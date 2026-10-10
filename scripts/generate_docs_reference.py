"""Generate the reference blocks in docs/ from the code.

The guides in docs/ hold blocks between

    <!-- BEGIN GENERATED: <name> -->
    <!-- END GENERATED: <name> -->

that this script rebuilds from the emulator itself, so they cannot drift:

- How each input column is read: found by running the emulator's own input
  path (PolicyEngineRunner, then TaxsimMicrosimDataset) on probe records and
  reading the PolicyEngine inputs it builds, and by writing the input file the
  TAXSIM-35 executable would receive.
- What each column means: docs/reference/input_variables.yaml, the one
  hand-written source. It must list exactly the columns the code reads.
- Where each output comes from: policyengine_taxsim/config/variable_mappings.yaml.
- Bundled executables: hashed and inspected from resources/.
- Python versions and dependencies: pyproject.toml, the CI workflow, and the
  dependency snapshots in docs/dependencies/.
- Worked examples: the files in docs/examples/custom-dataset/.

tests/test_docs_reference.py fails when a committed block differs from what
this script produces.

    python scripts/generate_docs_reference.py           # rewrite stale blocks
    python scripts/generate_docs_reference.py --check   # exit 1 if any is stale
    python scripts/generate_docs_reference.py --refresh-dependencies 2026-10-09T19:00:00Z
        # re-resolve docs/dependencies/ with uv as of that time (needs network)
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import io
import json
import math
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
INPUT_METADATA = DOCS / "reference" / "input_variables.yaml"
DEPENDENCIES = DOCS / "dependencies"
SNAPSHOT = DEPENDENCIES / "snapshot.json"
EXAMPLES = DOCS / "examples" / "custom-dataset"

BLOCK = re.compile(
    r"(<!-- BEGIN GENERATED: (?P<name>[\w-]+) -->\n)(?P<body>.*?)"
    r"(<!-- END GENERATED: (?P=name) -->)",
    re.S,
)

# Probe records: a 2023 California return, so every column is read in a year
# PolicyEngine computes and in a state with an income tax.
PROBE_YEAR = 2023
PROBE_STATE = 5
PROBE_AMOUNT = 1000.0
JOINT = {"year": PROBE_YEAR, "state": PROBE_STATE, "mstat": 2, "page": 40, "sage": 40}
SINGLE = {"year": PROBE_YEAR, "state": PROBE_STATE, "mstat": 1, "page": 40}

# The Python versions the dependency snapshots cover, and the platform they
# are resolved for (servers); other platforms are compared against it.
SNAPSHOT_PYTHONS = ("3.10", "3.11", "3.12", "3.13", "3.14")
SNAPSHOT_PLATFORM = "x86_64-manylinux_2_28"
OTHER_PLATFORMS = {
    "Windows (x86-64)": "x86_64-pc-windows-msvc",
    "macOS (Apple silicon)": "aarch64-apple-darwin",
}


# ---------------------------------------------------------------------------
# Reading the emulator's input path
# ---------------------------------------------------------------------------


class ProbeError(Exception):
    """The emulator's input path raised for a probe record."""


def read_inputs(record: dict) -> dict:
    """Run one record through PolicyEngineRunner's input path, stopping before
    the simulation.

    PolicyEngineRunner validates the record (statefip, state codes) and
    _run_once converts the year and splits the records into chunks. Each chunk
    normally goes to _run_chunk, which builds a TaxsimMicrosimDataset and
    simulates it; here the dataset is generated and kept instead. Returns the
    record as the dataset builder saw it after defaults ("frame") and the
    PolicyEngine input arrays it built ("inputs").
    """
    from policyengine_taxsim.runners.policyengine_runner import (
        PolicyEngineRunner,
        TaxsimMicrosimDataset,
    )

    seen = {}

    def keep_dataset(chunk_df):
        dataset = TaxsimMicrosimDataset.__new__(TaxsimMicrosimDataset)
        dataset.input_df = chunk_df.copy()
        frames = []
        build_people = dataset._process_person_data_for_year

        def watch(year_data, year):
            frames.append(year_data.copy())
            return build_people(year_data, year)

        dataset._process_person_data_for_year = watch
        data = {}
        dataset.save_dataset = data.update
        dataset.generate()
        year = int(frames[0]["year"].iloc[0])
        seen["frame"] = frames[0].iloc[0]
        seen["inputs"] = {
            name: np.asarray(by_year[year])
            for name, by_year in data.items()
            if year in by_year
        }
        return pd.DataFrame()

    key = json.dumps(record, sort_keys=True, default=str)
    if key in _PROBES:
        if isinstance(_PROBES[key], ProbeError):
            raise _PROBES[key]
        return _PROBES[key]
    quiet = io.StringIO()
    try:
        with contextlib.redirect_stderr(quiet), contextlib.redirect_stdout(quiet):
            runner = PolicyEngineRunner(pd.DataFrame([record]))
            runner._run_chunk = keep_dataset
            runner._run_once(show_progress=False, on_progress=None)
    except Exception as error:  # reported in the docs as the emulator's answer
        _PROBES[key] = ProbeError(f"{type(error).__name__}: {error}")
        raise _PROBES[key] from None
    _PROBES[key] = seen
    return seen


_PROBES = {}


def roles(inputs: dict) -> dict:
    """Person indices of the primary taxpayer, spouse and dependents."""
    return {
        "head": np.flatnonzero(inputs["is_tax_unit_head"]),
        "spouse": np.flatnonzero(inputs["is_tax_unit_spouse"]),
        "dependents": np.flatnonzero(inputs["is_tax_unit_dependent"]),
    }


def changed_inputs(with_value: dict, without: dict) -> dict:
    """PolicyEngine inputs that differ between two probes of one structure."""
    changed = {}
    for name, array in with_value["inputs"].items():
        other = without["inputs"].get(name)
        if other is None or array.shape != other.shape:
            continue
        if array.dtype.kind in "fiub" and not np.array_equal(array, other):
            changed[name] = array.astype(float) - other.astype(float)
    return changed


def read_taxsim_file(record: dict) -> dict:
    """The record as written to the input file of the TAXSIM-35 executable.

    Uses TaxsimRunner's own validation and file writer; the executable is not
    run, so this works on machines without it.
    """
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

    runner = TaxsimRunner.__new__(TaxsimRunner)
    runner.input_df = pd.DataFrame([record])
    runner._validate_input()
    path = Path(runner._create_taxsim_input_file(runner.input_df))
    try:
        written = pd.read_csv(path)
    finally:
        try:
            path.unlink()
        except OSError:  # as TaxsimRunner.run: Windows may still hold it
            pass
    return written.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# Input columns
# ---------------------------------------------------------------------------


def load_input_metadata() -> dict:
    with open(INPUT_METADATA, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def read_columns() -> set:
    """Every input column either engine reads.

    TaxsimRunner.ALL_COLUMNS is what pre-2021 rows pass to TAXSIM-35 and what
    PolicyEngineRunner fills in when missing; PolicyEngine rows also read
    age11 and every column named in the input mapping; statefip is resolved
    for both engines by BaseTaxRunner.
    """
    from policyengine_taxsim.core.utils import load_variable_mappings
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

    mappings = load_variable_mappings()
    columns = set(TaxsimRunner.ALL_COLUMNS) | {"statefip"}
    columns |= {f"age{slot}" for slot in range(1, DEPENDENT_SLOTS + 1)}
    for item in mappings["taxsim_input_definition"]:
        columns |= set(item)
    situation = mappings["taxsim_to_policyengine"]["household_situation"]
    for key in ("additional_income_units", "additional_tax_units"):
        for item in situation[key]:
            for sources in item.values():
                columns |= {
                    source
                    for source in sources or []
                    if source in TaxsimRunner.ALL_COLUMNS
                }
    return columns


# PolicyEngineRunner reads dependent ages from age1 to age11
# (_process_person_data_for_year); the input-handling table confirms by probe.
DEPENDENT_SLOTS = 11

GROUP_ORDER = (
    "Record and filing unit",
    "Dependents",
    "Wages and self-employment",
    "Business income (QBI)",
    "Investment and other income",
    "Retirement and benefits",
    "Deductions and expenses",
    "Output and options",
)


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def column_order(metadata: dict) -> list:
    order = []
    for group in GROUP_ORDER:
        order += [name for name, entry in metadata.items() if entry["group"] == group]
    unknown = set(metadata) - set(order)
    if unknown:
        raise ValueError(f"Columns with an unknown group: {sorted(unknown)}")
    return order


def block_input_columns() -> str:
    metadata = load_input_metadata()
    lines = []
    for group in GROUP_ORDER:
        names = [n for n in column_order(metadata) if metadata[n]["group"] == group]
        if not names:
            continue
        lines += [f"#### {group}", "", "| Column | Meaning | Type | Valid values |"]
        lines.append("|---|---|---|---|")
        for name in names:
            if re.fullmatch(r"age([2-9]|1[01])", name):
                continue  # age2..age11 share age1's row
            entry = metadata[name]
            label = "`age1` to `age11`" if name == "age1" else f"`{name}`"
            lines.append(
                f"| {label} | {_cell(entry['meaning'])} | {_cell(entry['type'])}"
                f" | {_cell(entry['valid'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def _number(value) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _probe_value(column: str) -> float:
    return 7.0 if column.startswith("age") else PROBE_AMOUNT


def _base_for(column: str) -> dict:
    """A probe record that lets ``column`` take effect."""
    if column.startswith("age"):
        return {**JOINT, "depx": DEPENDENT_SLOTS}
    return dict(JOINT)


def _effective_value(column: str, seen: dict) -> str:
    """The value a column ends up with in the dataset the emulator builds."""
    match = re.fullmatch(r"age(\d+)", column)
    if match:
        dependents = roles(seen["inputs"])["dependents"]
        return _number(seen["inputs"]["age"][dependents[int(match.group(1)) - 1]])
    frame = seen["frame"]
    return _number(frame[column]) if column in frame.index else "Not read"


def blank_handling(column: str, used: bool) -> tuple[str, str]:
    """What a blank cell and a left-out column become on PolicyEngine rows,
    as the dataset builder sees them after defaults, or the error the
    emulator stops with."""
    if not used:
        return "Not used", "Not used"
    if column == "statefip":
        return "`state` is used", "`state` is used"
    if column == "taxsimid":
        return "Blank in the output", "Records numbered 1, 2, 3, ..."
    results = []
    for mode in ("blank", "omit"):
        record = _base_for(column)
        if mode == "omit":
            record.pop(column, None)
        else:
            record[column] = math.nan
        try:
            results.append(_effective_value(column, read_inputs(record)))
        except ProbeError:
            results.append("The run stops with an error")
    blank, absent = results
    if column != "year":
        zero = _effective_value(column, read_inputs({**_base_for(column), column: 0}))
        if zero != "0":
            blank += f"; 0 also becomes {zero}"
    return blank, absent


def _single_share(column: str, variable: str) -> float:
    """What the primary taxpayer of a one-adult return gets from ``column``."""
    with_value = read_inputs({**SINGLE, column: PROBE_AMOUNT})
    without = read_inputs({**SINGLE, column: 0})
    delta = changed_inputs(with_value, without).get(variable)
    return 0.0 if delta is None else float(delta.sum())


def amount_target(column: str) -> str:
    """Which PolicyEngine input an amount column feeds, and who gets it, read
    from probes of a joint and a one-adult return."""
    amount = PROBE_AMOUNT
    joint = read_inputs({**JOINT, column: amount})
    changed = changed_inputs(joint, read_inputs({**JOINT, column: 0}))
    if not changed:
        return "Not used: no effect on PolicyEngine rows"
    n_people = len(joint["inputs"]["is_tax_unit_head"])
    who = roles(joint["inputs"])
    parts = []
    for variable, delta in sorted(changed.items()):
        if delta.shape[0] != n_people:
            parts.append(f"`{variable}` of the tax unit")
            continue
        head = float(delta[who["head"]].sum())
        spouse = float(delta[who["spouse"]].sum())
        single = _single_share(column, variable)
        if math.isclose(head, amount) and spouse == 0 and math.isclose(single, amount):
            parts.append(f"`{variable}` of the primary taxpayer")
        elif head == 0 and math.isclose(spouse, amount) and single == 0:
            parts.append(f"`{variable}` of the spouse; ignored unless `mstat` is 2")
        elif (
            math.isclose(head, amount / 2)
            and math.isclose(spouse, amount / 2)
            and math.isclose(single, amount)
        ):
            text = f"`{variable}`, split evenly between spouses on joint returns"
            if _older_spouse_takes_all(column, variable):
                text += (
                    ", or all to the older spouse when only one has reached "
                    "the age threshold (see below)"
                )
            parts.append(text)
        else:
            raise ValueError(
                f"{column}: unrecognized allocation of {variable} "
                f"(joint {head}/{spouse}, single {single}). Extend "
                "scripts/generate_docs_reference.py to describe it."
            )
    return "; ".join(parts)


def policyengine_targets(columns) -> dict:
    """Column -> description of the PolicyEngine input it feeds. Columns that
    feed the same variable for the same person say so."""
    targets = {}
    for column in columns:
        structural = _structural_target(column)
        targets[column] = structural if structural else amount_target(column)
    by_target = defaultdict(list)
    for column, target in targets.items():
        if target.startswith("`") and ";" not in target:
            by_target[target].append(column)
    for target, sharing in by_target.items():
        for column in sharing:
            others = [other for other in sharing if other != column]
            if others:
                targets[column] = (
                    target + ", summed with " + " and ".join(f"`{o}`" for o in others)
                )
    return targets


def _older_spouse_takes_all(column: str, variable: str) -> bool:
    record = {**JOINT, "page": 70, "sage": 40, column: PROBE_AMOUNT}
    seen = read_inputs(record)
    who = roles(seen["inputs"])
    values = seen["inputs"][variable]
    return math.isclose(values[who["head"]].sum(), PROBE_AMOUNT) and math.isclose(
        values[who["spouse"]].sum(), 0
    )


def _ages(record: dict) -> list:
    seen = read_inputs(record)
    who = roles(seen["inputs"])
    return [int(age) for age in seen["inputs"]["age"][who["dependents"]]]


def _structural_target(column: str) -> str | None:
    """Columns that shape the tax unit rather than add an amount. Each claim is
    checked against a probe; a failed check stops the generator."""

    def check(condition, claim):
        if not condition:
            raise ValueError(f"{column}: the emulator no longer does this: {claim}")

    if column == "taxsimid":
        return "None: returned as `taxsimid`"
    if column == "year":
        seen = read_inputs({**SINGLE, "year": 2024})
        check(seen["frame"]["year"] == 2024, "year sets the period")
        return "The period every variable is computed for"
    if column == "state":
        ny = read_inputs({**SINGLE, "state": 33})["inputs"]["state_fips"]
        none = read_inputs({**SINGLE, "state": 0})["inputs"]["state_fips"]
        check(list(ny) == [36] and list(none) == [48], "SOI -> FIPS, 0 -> Texas")
        return (
            "`state_fips`, converted from the SOI code. State 0 is computed as "
            "Texas, which has no income tax, and reported as 0"
        )
    if column == "statefip":
        seen = read_inputs({**SINGLE, "state": 0, "statefip": 36})
        check(list(seen["inputs"]["state_fips"]) == [36], "statefip -> state_fips")
        return "`state_fips` (converted to `state` first)"
    if column == "mstat":
        return mstat_handling()
    if column == "page":
        seen = read_inputs({**SINGLE, "page": 70})
        who = roles(seen["inputs"])
        check(seen["inputs"]["age"][who["head"]].tolist() == [70], "page -> age")
        return "`age` of the primary taxpayer"
    if column == "sage":
        joint = read_inputs({**JOINT, "sage": 70})
        who = roles(joint["inputs"])
        check(joint["inputs"]["age"][who["spouse"]].tolist() == [70], "sage -> age")
        single = read_inputs({**SINGLE, "sage": 70})
        check(len(roles(single["inputs"])["spouse"]) == 0, "no spouse when single")
        return "`age` of the spouse (joint returns only)"
    if column == "depx":
        seen = read_inputs({**SINGLE, "depx": 3})
        check(len(roles(seen["inputs"])["dependents"]) == 3, "depx -> dependents")
        return "Number of dependents added to the tax unit"
    match = re.fullmatch(r"age(\d+)", column)
    if match:
        slot = int(match.group(1))
        ages = _ages({**JOINT, "depx": DEPENDENT_SLOTS, column: 7})
        check(ages[slot - 1] == 7, f"{column} -> dependent {slot}")
        return f"`age` of dependent {slot}"
    if column in ("dep13", "dep17", "dep18"):
        ages = _ages({**SINGLE, "depx": 4, "dep13": 1, "dep17": 2, "dep18": 3})
        check(ages == [10, 15, 17, 21], "dependent counts -> ages 10, 15, 17, 21")
        return "Dependent `age`s 10, 15, 17 and 21 (see `dep13`)"
    if column == "idtl":
        return "None: selects the output columns"
    return None


MSTAT_PROBES = tuple(range(1, 10))


def _mstat_structure(code: int) -> tuple:
    seen = read_inputs({**SINGLE, "mstat": code, "sage": 40})
    inputs = seen["inputs"]
    return (
        len(roles(inputs)["spouse"]) > 0,
        bool(np.any(inputs["is_separated"])),
        bool(np.any(inputs["cohabitating_spouses"])),
    )


def mstat_handling() -> str:
    """How each filing-status code from 1 to 9 shapes the tax unit, read from
    probes."""
    groups = defaultdict(list)
    for code in MSTAT_PROBES:
        groups[_mstat_structure(code)].append(code)
    sentences = []
    for (spouse, separated, cohabiting), codes in sorted(
        groups.items(), key=lambda item: len(item[1])
    ):
        if spouse:
            sentences.append(f"{_codes(codes)}: a spouse is added to the tax unit")
        elif separated and cohabiting:
            sentences.append(
                f"{_codes(codes)}: one adult, with `is_separated` and "
                "`cohabitating_spouses` set"
            )
        elif not separated and not cohabiting:
            sentences.append(f"{_codes(codes)}: one adult, treated as unmarried")
        else:
            raise ValueError(f"mstat {codes}: unrecognized structure")
    return ". ".join(sentences)


def _codes(codes) -> str:
    codes = [str(c) for c in codes]
    return codes[0] if len(codes) == 1 else ", ".join(codes[:-1]) + " and " + codes[-1]


def taxsim_handling(column: str) -> str:
    """What pre-2021 rows pass to the TAXSIM-35 executable for a column."""
    if column == "taxsimid":
        return "Passed"
    if column in ("dep13", "dep17", "dep18"):
        written = read_taxsim_file(
            {**SINGLE, "year": 2019, "depx": 4, "dep13": 1, "dep17": 2, "dep18": 3}
        )
        ages = [written.get(f"age{slot}") for slot in range(1, 5)]
        if ages == [10, 15, 17, 21] and column not in written:
            return "Converted to ages first"
        return "Passed" if column in written else "Not passed"
    if column == "statefip":
        written = read_taxsim_file({**SINGLE, "year": 2019, "state": 0, column: 36})
        if column not in written and written["state"] == 33:
            return "Converted to `state` first"
        return "Passed" if column in written else "Not passed"
    value = _probe_value(column)
    record = {**_base_for(column), "year": 2019, column: value}
    written = read_taxsim_file(record)
    if column not in written:
        return "Not passed"
    if float(written[column]) != value:
        raise ValueError(f"{column}: TAXSIM-35 receives {written[column]}, not {value}")
    return "Passed"


def block_input_handling() -> str:
    metadata = load_input_metadata()
    columns = column_order(metadata)
    targets = policyengine_targets(columns)
    lines = [
        "| Column | Blank cell | Column left out | PolicyEngine input (2021 and later) | Pre-2021 rows, to TAXSIM-35 |",
        "|---|---|---|---|---|",
    ]
    for name in columns:
        target = targets[name]
        blank, absent = blank_handling(name, not target.startswith("Not used"))
        lines.append(
            f"| `{name}` | {_cell(blank)} | {_cell(absent)} | {_cell(target)}"
            f" | {taxsim_handling(name)} |"
        )
    return "\n".join(lines) + "\n"


def block_pension_split_ages() -> str:
    """The age thresholds for allocating pensions and Social Security between
    spouses, read from PolicyEngineRunner and checked by probes."""
    from policyengine_taxsim.core.utils import STATE_NUMBERS
    from policyengine_taxsim.runners.policyengine_runner import (
        TaxsimMicrosimDataset as D,
    )

    default = D._DEFAULT_PENSION_SPLIT_AGE
    for column in ("pensions", "gssi"):
        straddle = {**JOINT, "page": default, "sage": default - 1, column: 1000}
        seen = read_inputs(straddle)
        variable = (
            "taxable_private_pension_income"
            if column == "pensions"
            else "social_security_retirement"
        )
        who = roles(seen["inputs"])
        if seen["inputs"][variable][who["head"]].sum() != 1000:
            raise ValueError(f"{column}: default threshold is no longer {default}")
    lines = [
        f"- Default threshold: {default}, for `gssi` in every state and for "
        "`pensions` in states not listed below.",
    ]
    for state, age in sorted(D._PENSION_SPLIT_AGE_BY_STATE.items()):
        record = {
            **JOINT,
            "state": STATE_NUMBERS[state],
            "page": max(age, 1),
            "sage": max(age - 1, 0),
            "pensions": 1000,
        }
        seen = read_inputs(record)
        who = roles(seen["inputs"])
        head = seen["inputs"]["taxable_private_pension_income"][who["head"]].sum()
        if age == 0:
            if head != 500:
                raise ValueError(f"{state}: pensions no longer always split")
            lines.append(f"- `pensions` in {state}: always split evenly.")
        else:
            if head != 1000:
                raise ValueError(f"{state}: pension threshold is no longer {age}")
            lines.append(f"- `pensions` in {state}: {age}.")
    return "\n".join(lines) + "\n"


def block_state_codes() -> str:
    from policyengine_taxsim.core.utils import SOI_TO_FIPS_MAP, STATE_MAPPING

    rows = [(soi, STATE_MAPPING[soi], SOI_TO_FIPS_MAP[soi]) for soi in STATE_MAPPING]
    per_line = 4
    header = "| " + " | ".join(["SOI | State | FIPS"] * per_line) + " |"
    rule = "|" + "---|" * (3 * per_line)
    lines = [header, rule]
    for start in range(0, len(rows), per_line):
        chunk = rows[start : start + per_line]
        cells = [f"{soi} | {code} | {fips}" for soi, code, fips in chunk]
        cells += ["  |  | "] * (per_line - len(chunk))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def block_example(name: str):
    language = {".py": "python", ".do": "stata", ".R": "r", ".csv": "csv"}

    def render() -> str:
        path = EXAMPLES / name
        fence = language[path.suffix]
        return f"```{fence}\n{path.read_text(encoding='utf-8').rstrip()}\n```\n"

    return render


# Dataset entries that describe the tax unit's structure rather than set a
# policy input; left out of the fixed-inputs list.
STRUCTURE = re.compile(
    r"^(person_\w*id|\w+_id|\w+_weight|is_tax_unit_\w+|age|state_fips|"
    r"is_separated|cohabitating_spouses)$"
)


def block_fixed_inputs() -> str:
    """PolicyEngine inputs the dataset builder sets on every record whatever
    the input file says, read from the dataset built for a minimal record."""
    from policyengine_taxsim.runners.policyengine_runner import (
        TaxsimMicrosimDataset,
    )

    dataset = TaxsimMicrosimDataset.__new__(TaxsimMicrosimDataset)
    fed_by_columns = set(dataset._get_taxsim_to_pe_variable_mapping())
    fed_by_columns |= set(dataset._get_tax_unit_variable_mapping())
    seen = read_inputs({"year": PROBE_YEAR, "state": PROBE_STATE})
    lines = []
    for name, values in sorted(seen["inputs"].items()):
        if name in fed_by_columns or STRUCTURE.match(name):
            continue
        if values.dtype.kind not in "fiub":
            continue
        distinct = np.unique(values)
        value = _number(distinct[0]) if len(distinct) == 1 else "varies"
        lines.append(f"- `{name}` = {value}")
    return "\n".join(lines) + "\n"


def run_time_pins() -> list:
    """Variables PolicyEngineRunner holds fixed on the Microsimulation, read
    by building one for a chunk that meets every condition in
    _build_configured_sim and recording each _pin_input call.

    Not a generated block: which variables exist depends on the installed
    policyengine-us, so tests/test_docs_reference.py only checks that each
    one appears in docs/design.md."""
    from policyengine_taxsim.runners import policyengine_runner as module

    chunk = pd.DataFrame(
        [
            {**SINGLE, "taxsimid": 1, "state": 0, "otherprop": 1000},
            {**SINGLE, "taxsimid": 2, "state": 24, "rentpaid": 9000},
            {**SINGLE, "taxsimid": 3, "state": 20, "rentpaid": 9000},
            {**SINGLE, "taxsimid": 4, "state": 21, "pwages": 50000},
            {**SINGLE, "taxsimid": 5, "state": 33, "pwages": 50000},
        ]
    )
    pinned = []
    real_pin = module._pin_input

    def record(sim, variable_name, value, period):
        pinned.append(variable_name)
        return real_pin(sim, variable_name, value, period)

    quiet = io.StringIO()
    with contextlib.redirect_stderr(quiet), contextlib.redirect_stdout(quiet):
        runner = module.PolicyEngineRunner(
            chunk.copy(), disable_salt=True, assume_w2_wages=True
        )
        dataset = module.TaxsimMicrosimDataset(runner.input_df)
        try:
            dataset.generate()
            module._pin_input = record
            runner._build_configured_sim(dataset, runner.input_df, zero_salt=True)
        finally:
            module._pin_input = real_pin
            dataset.cleanup()
    return sorted(set(pinned))


def block_one_time_rebates() -> str:
    from policyengine_taxsim.core.state_output_resolver import (
        ONE_TIME_REBATE_VARIABLES,
    )

    return ", ".join(f"`{name}`" for name in ONE_TIME_REBATE_VARIABLES) + "\n"


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

# Outputs that _extract_vectorized_results adjusts after the variable in the
# mapping file is computed. Each note names a marker that must still appear
# in that method (or a file that must exist), so a removed adjustment stops
# the generator instead of leaving a stale note.
OUTPUT_NOTES = {
    "fiitax": (
        "tests/test_addmed_excluded_from_fiitax.py",
        "Includes the net investment income tax but not the Additional "
        "Medicare Tax, which is in `fica`, `tfica` and `addmed`",
    ),
    "v22": (
        'if "v22" in columns',
        "In years when the credit is not fully refundable, capped at "
        "`ctc_limiting_tax_liability`, so it reports the non-refundable part",
    ),
    "v40": (
        'if "v40" in columns and rebate_free_sim is not None',
        "Summed with one-time state rebates set to 0; they are reported in "
        "`srebate` instead",
    ),
    "staxbc": (
        "_apply_de_staxbc_elected_path",
        "For Delaware couples who elect to file separately on a combined "
        "return, the sum of the two separate taxes",
    ),
}


def _output_note(name: str) -> str:
    from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

    if name not in OUTPUT_NOTES:
        return ""
    marker, note = OUTPUT_NOTES[name]
    source = inspect.getsource(PolicyEngineRunner._extract_vectorized_results)
    if marker not in source and not (REPO / marker).exists():
        raise ValueError(f"{name}: the adjustment marked {marker!r} is gone")
    return f". {note}"


def block_output_sources() -> str:
    from policyengine_taxsim.core.state_output_resolver import (
        has_state_variable_mapping,
        is_output_adapter,
    )
    from policyengine_taxsim.core.utils import load_variable_mappings

    outputs = load_variable_mappings()["policyengine_to_taxsim"]
    lines = [
        "| Output | TAXSIM-35 description | Computed from | idtl |",
        "|---|---|---|---|",
    ]
    for name, mapping in outputs.items():
        variable = mapping.get("variable", "")
        variables = mapping.get("variables") or []
        levels = ", ".join(
            str(level) for entry in mapping.get("idtl", []) for level in entry.values()
        )
        if not mapping.get("implemented", False):
            source = "Not produced on PolicyEngine rows"
        elif variable in ("taxsimid", "get_year", "get_state_code"):
            source = "The input value"
        elif variable == "na_pe":
            source = "Always 0 on PolicyEngine rows"
        elif variable == "marginal_rate_computed":
            base = "income_tax" if name == "frate" else "state_income_tax"
            source = f"Change in `{base}` when wages rise by $100, as a percentage"
        elif variable == "srebate_computed":
            source = (
                "`state_income_tax` with one-time state rebates set to 0, "
                "minus `state_income_tax`"
            )
        elif has_state_variable_mapping(mapping):
            states = len([s for s, v in mapping["state_variables"].items() if v])
            source = f"A state-specific variable ({states} states mapped)"
        elif is_output_adapter(variable):
            source = f"`{variable}` adapter (state-specific rules)"
        elif variables:
            source = " + ".join(f"`{v}`" for v in variables)
        else:
            source = f"`{variable}`"
        description = mapping.get("text_description", "")
        source += _output_note(name)
        lines.append(f"| `{name}` | {_cell(description)} | {source} | {levels} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Bundled executables
# ---------------------------------------------------------------------------


def _binary_kind(data: bytes) -> str:
    if data[:4] == b"\x7fELF":
        machine = int.from_bytes(data[18:20], "little")
        return {0x3E: "Linux ELF, x86-64", 0xB7: "Linux ELF, arm64"}.get(
            machine, f"Linux ELF, machine {machine:#x}"
        )
    if data[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
        cpu = int.from_bytes(data[4:8], "little")
        return {
            0x01000007: "macOS Mach-O, x86-64",
            0x0100000C: "macOS Mach-O, arm64",
        }.get(cpu, "macOS Mach-O")
    if data[:2] == b"MZ":
        offset = int.from_bytes(data[0x3C:0x40], "little")
        machine = int.from_bytes(data[offset + 4 : offset + 6], "little")
        return {0x8664: "Windows PE, x86-64", 0x14C: "Windows PE, 32-bit x86"}.get(
            machine, "Windows PE"
        )
    return "Unknown"


def _build_stamp(data: bytes) -> str:
    match = re.search(rb"cd\d{10}|cdate-\d{4}[A-Za-z]{3}\d{1,2}", data)
    return match.group(0).decode() if match else "Not found"


def run_time_binaries() -> dict:
    """The executable TaxsimRunner picks on each operating system."""
    import platform
    from unittest import mock

    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

    detect = TaxsimRunner.__dict__["_detect_taxsim_executable"]
    detect = detect.__func__ if isinstance(detect, staticmethod) else detect
    takes_self = len(inspect.signature(detect).parameters) == 1
    picked = {}
    for system in ("Darwin", "Linux", "Windows"):
        with mock.patch.object(platform, "system", return_value=system):
            path = detect(None) if takes_self else detect()
        picked[path.name] = system
    return picked


def block_taxsim_binaries() -> str:
    picked = run_time_binaries()
    lines = [
        "| File | Format | Build stamp | Bytes | SHA-256 | Run by the emulator |",
        "|---|---|---|---|---|---|",
    ]
    for path in sorted((REPO / "resources").glob("*/*.exe")):
        data = path.read_bytes()
        used = picked.get(path.name)
        lines.append(
            f"| `{path.relative_to(REPO).as_posix()}` | {_binary_kind(data)} | "
            f"{_build_stamp(data)} | {len(data):,} | `{hashlib.sha256(data).hexdigest()}` | "
            f"{'Yes, on ' + {'Darwin': 'macOS'}.get(used, used) if used else 'No (tests only)'} |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Python versions and dependencies
# ---------------------------------------------------------------------------


def _pyproject() -> dict:
    try:
        import tomllib
    except ImportError:  # Python 3.10
        import tomli as tomllib
    with open(REPO / "pyproject.toml", "rb") as stream:
        return tomllib.load(stream)


def block_python_versions() -> str:
    project = _pyproject()["project"]
    with open(REPO / ".github" / "workflows" / "ci.yml", encoding="utf-8") as stream:
        ci = yaml.safe_load(stream)
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    lines = [
        f"- `pyproject.toml` requires Python `{project['requires-python']}`.",
        "- CI runs the test suite on "
        + ", ".join(f"`{os}`" for os in matrix["os"])
        + " with Python "
        + " and ".join(str(v) for v in matrix["python-version"])
        + ".",
        f"- As of {snapshot['exclude_newer']}, the latest policyengine-us "
        f"({snapshot['policyengine_us_latest']['version']}) requires Python "
        f"`{snapshot['policyengine_us_latest']['requires_python']}`. Which "
        "policyengine-us each Python version installs:",
        "",
        "| Python | policyengine-us | policyengine-core |",
        "|---|---|---|",
    ]
    for python in SNAPSHOT_PYTHONS:
        versions = snapshot["linux"][python]
        lines.append(
            f"| {python} | {versions.get('policyengine-us', '-')} | "
            f"{versions.get('policyengine-core', '-')} |"
        )
    return "\n".join(lines) + "\n"


def block_direct_dependencies() -> str:
    project = _pyproject()["project"]
    lines = ["| Requirement | Installed |", "|---|---|"]
    for requirement in project["dependencies"]:
        lines.append(f"| `{requirement}` | Always |")
    for extra, requirements in project.get("optional-dependencies", {}).items():
        for requirement in requirements:
            lines.append(
                f"| `{requirement}` | Only with `policyengine-taxsim[{extra}]` |"
            )
    return "\n".join(lines) + "\n"


def parse_requirements(path: Path) -> dict:
    """name -> (version, [required by]) from a `uv pip compile` file."""
    packages = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+)", line)
        if match:
            current = match.group(1).lower()
            packages[current] = (match.group(2), [])
            continue
        match = re.match(r"^\s+#\s+(?:via\s+)?([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if match and current and match.group(1).lower() != "via":
            packages[current][1].append(match.group(1).lower())
    return packages


def block_dependency_tree() -> str:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    resolved = {
        python: parse_requirements(DEPENDENCIES / f"requirements-py{python}.txt")
        for python in SNAPSHOT_PYTHONS
    }
    names = sorted(set().union(*resolved.values()))
    header = (
        "| Package | " + " | ".join(SNAPSHOT_PYTHONS) + " | Required by | License |"
    )
    lines = [header, "|---|" + "---|" * (len(SNAPSHOT_PYTHONS) + 2)]
    for name in names:
        versions = [
            resolved[python][name][0] if name in resolved[python] else "-"
            for python in SNAPSHOT_PYTHONS
        ]
        required_by = sorted(
            {
                source
                for python in SNAPSHOT_PYTHONS
                if name in resolved[python]
                for source in resolved[python][name][1]
            }
        )
        licence = snapshot["licenses"].get(name, "Not recorded")
        lines.append(
            f"| {name} | "
            + " | ".join(versions)
            + f" | {', '.join(required_by)} | {_cell(licence)} |"
        )
    counts = ", ".join(
        f"{len(resolved[python])} on Python {python}" for python in SNAPSHOT_PYTHONS
    )
    lines += ["", f"Packages, not counting policyengine-taxsim itself: {counts}."]
    lines += ["", "Packages that differ from Linux on other platforms:", ""]
    for label, platform in OTHER_PLATFORMS.items():
        groups = []  # [pythons, added, removed], consecutive versions merged
        for python in SNAPSHOT_PYTHONS:
            linux = set(snapshot["linux"][python])
            other = set(snapshot["platforms"][platform][python])
            added, removed = sorted(other - linux), sorted(linux - other)
            if groups and groups[-1][1:] == [added, removed]:
                groups[-1][0].append(python)
            else:
                groups.append([[python], added, removed])
        differences = []
        for pythons, added, removed in groups:
            if not (added or removed):
                continue
            parts = []
            if added:
                parts.append("adds " + ", ".join(added))
            if removed:
                parts.append("leaves out " + ", ".join(removed))
            span = pythons[0] if len(pythons) == 1 else f"{pythons[0]} to {pythons[-1]}"
            differences.append(f"on Python {span}, " + "; ".join(parts))
        lines.append(f"- {label}: " + ("; ".join(differences) or "none") + ".")
    return "\n".join(lines) + "\n"


def block_snapshot_command() -> str:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return (
        "```bash\n"
        f"python scripts/generate_docs_reference.py --refresh-dependencies "
        f"{snapshot['exclude_newer']}\n```\n\n"
        f"The committed snapshot was resolved with {snapshot['resolver']} for "
        f"`{SNAPSHOT_PLATFORM}` and packages published before "
        f"{snapshot['exclude_newer']}.\n"
    )


def refresh_dependencies(exclude_newer: str) -> None:
    """Re-resolve the dependency snapshots with uv (needs network)."""
    DEPENDENCIES.mkdir(parents=True, exist_ok=True)
    resolver = subprocess.run(
        ["uv", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()

    def compile_set(python, platform, output, hashes):
        command = [
            "uv",
            "pip",
            "compile",
            "pyproject.toml",
            "--quiet",
            "--python-version",
            python,
            "--python-platform",
            platform,
            "--exclude-newer",
            exclude_newer,
            "-o",
            str(output),
        ]
        if hashes:
            command.append("--generate-hashes")
        shown = " ".join(
            ["uv pip compile pyproject.toml", "--python-version", python]
            + ["--python-platform", platform, "--exclude-newer", exclude_newer]
            + (["--generate-hashes"] if hashes else [])
            + ["-o", f"docs/dependencies/{output.name}"]
        )
        command += ["--custom-compile-command", shown]
        subprocess.run(command, cwd=REPO, check=True)
        return {
            name: version for name, (version, _) in parse_requirements(output).items()
        }

    linux, platforms = {}, {platform: {} for platform in OTHER_PLATFORMS.values()}
    scratch = DEPENDENCIES / ".scratch.txt"
    for python in SNAPSHOT_PYTHONS:
        output = DEPENDENCIES / f"requirements-py{python}.txt"
        linux[python] = compile_set(python, SNAPSHOT_PLATFORM, output, hashes=True)
        for platform in OTHER_PLATFORMS.values():
            platforms[platform][python] = compile_set(python, platform, scratch, False)
    scratch.unlink()

    licenses = {}
    every = {
        (name, version)
        for sets in [linux, *platforms.values()]
        for packages in sets.values()
        for name, version in packages.items()
    }
    for name, version in sorted(every):
        if name not in licenses:
            licenses[name] = _pypi_license(name, version)
    SNAPSHOT.write_text(
        json.dumps(
            {
                "exclude_newer": exclude_newer,
                "resolver": resolver,
                "policyengine_us_latest": _newest_release(
                    "policyengine-us", exclude_newer
                ),
                "linux": linux,
                "platforms": platforms,
                "licenses": licenses,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _newest_release(name: str, before: str) -> dict:
    """The highest version of ``name`` uploaded to PyPI before ``before``."""
    releases = _pypi_json(name)["releases"]

    def key(version):
        return tuple(int(part) for part in re.findall(r"\d+", version))

    uploaded = [
        version
        for version, files in releases.items()
        if files and min(f["upload_time_iso_8601"] for f in files) < before
    ]
    newest = max(uploaded, key=key)
    return {
        "version": newest,
        "requires_python": _pypi_json(name, newest)["info"]["requires_python"],
    }


def _pypi_json(name: str, version: str | None = None) -> dict:
    url = f"https://pypi.org/pypi/{name}/{version + '/' if version else ''}json"
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def _pypi_license(name: str, version: str) -> str:
    """The license a package declares on PyPI: its SPDX expression, else a
    short license field, else its license classifiers, else the family its
    license text belongs to."""
    info = _pypi_json(name, version)["info"]
    expression = info.get("license_expression")
    if expression:
        return expression
    text = (info.get("license") or "").strip()
    if text and len(text) <= 60 and "\n" not in text:
        return text
    classifiers = [
        c.split(" :: ")[-1]
        for c in info.get("classifiers") or []
        if c.startswith("License ::") and c != "License :: OSI Approved"
    ]
    if classifiers:
        return ", ".join(classifiers)
    for phrase, family in (
        ("Redistribution and use in source and binary forms", "BSD-style"),
        ("Permission is hereby granted, free of charge", "MIT-style"),
        ("Apache License", "Apache"),
    ):
        if phrase in text:
            return f"{family} (full text in metadata)"
    return "See the package's metadata"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

GENERATED = {
    "input-guide.md": {
        "input-columns": block_input_columns,
        "input-handling": block_input_handling,
        "pension-split-ages": block_pension_split_ages,
        "state-codes": block_state_codes,
        "example-survey-csv": block_example("survey_extract.csv"),
        "example-python": block_example("crosswalk.py"),
        "example-stata": block_example("crosswalk.do"),
        "example-r": block_example("crosswalk.R"),
    },
    "design.md": {
        "fixed-inputs": block_fixed_inputs,
        "one-time-rebates": block_one_time_rebates,
        "output-sources": block_output_sources,
    },
    "security-and-deployment.md": {
        "python-versions": block_python_versions,
        "direct-dependencies": block_direct_dependencies,
        "dependency-tree": block_dependency_tree,
        "snapshot-command": block_snapshot_command,
        "taxsim-binaries": block_taxsim_binaries,
    },
}


def render(document: str, text: str) -> str:
    """``text`` with every generated block of ``document`` rebuilt."""
    generators = GENERATED[document]
    found = set()

    def replace(match):
        name = match.group("name")
        if name not in generators:
            raise ValueError(f"docs/{document}: no generator for block {name!r}")
        found.add(name)
        return match.group(1) + generators[name]() + match.group(4)

    rendered = BLOCK.sub(replace, text)
    missing = set(generators) - found
    if missing:
        raise ValueError(f"docs/{document}: missing blocks {sorted(missing)}")
    return rendered


def stale_documents() -> list:
    stale = []
    for document in GENERATED:
        path = DOCS / document
        text = path.read_text(encoding="utf-8")
        if render(document, text) != text:
            stale.append(document)
    return stale


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if stale")
    parser.add_argument(
        "--refresh-dependencies",
        metavar="TIMESTAMP",
        help="re-resolve docs/dependencies/ with uv for packages published "
        "before TIMESTAMP (needs network)",
    )
    args = parser.parse_args(argv)
    if args.refresh_dependencies:
        refresh_dependencies(args.refresh_dependencies)
    if args.check:
        stale = stale_documents()
        for document in stale:
            print(f"docs/{document} is out of date", file=sys.stderr)
        if stale:
            print("Run: python scripts/generate_docs_reference.py", file=sys.stderr)
        return 1 if stale else 0
    for document in GENERATED:
        path = DOCS / document
        text = path.read_text(encoding="utf-8")
        rendered = render(document, text)
        if rendered != text:
            path.write_text(rendered, encoding="utf-8", newline="\n")
            print(f"Updated docs/{document}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
