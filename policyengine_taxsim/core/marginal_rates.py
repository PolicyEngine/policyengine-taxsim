"""TAXSIM-compatible marginal tax rate computation.

Matches TAXSIM-35 methodology:
- Perturbs wages split proportionally between primary and spouse
  (weighted average earnings)
- Only perturbs employment income (wages), not self-employment
- Returns rates as percentages (22.0 for 22%)

Note: TAXSIM uses $0.01 delta with Fortran float64 precision.
PolicyEngine uses float32 internally, so we use $100 delta to
avoid precision loss while remaining small enough to stay within
a single tax bracket for most filers.
"""

import copy
from policyengine_us import Simulation


DELTA = 100.0  # $100: large enough for float32 precision, small for bracket safety


def compute_marginal_rates_single(simulation, situation, year, disable_salt):
    """Compute marginal rates for a single household (exe/output_mapper path).

    Args:
        simulation: Base PolicyEngine Simulation (already computed).
        situation: The situation dict used to create the simulation.
        year: Tax year string.
        disable_salt: Whether SALT deduction is disabled.

    Returns:
        dict with 'frate', 'srate', 'ficar' as percentage values.
    """
    people = situation["people"]

    # Get base tax values from the existing simulation
    # frate must match fiitax definition: income_tax + additional_medicare_tax
    base_federal = float(simulation.calculate("income_tax", period=year)[0]) + float(
        simulation.calculate("additional_medicare_tax", period=year)[0]
    )
    base_state = float(simulation.calculate("state_income_tax", period=year)[0])

    # Get current wages
    pwages = float(people["you"].get("employment_income", {}).get(year, 0))
    swages = 0.0
    if "your partner" in people:
        swages = float(people["your partner"].get("employment_income", {}).get(year, 0))

    total_wages = pwages + swages

    # Compute proportional split (TAXSIM: weighted average earnings)
    if total_wages > 0:
        p_share = pwages / total_wages
        s_share = swages / total_wages
    else:
        p_share = 0.5
        s_share = 0.5 if "your partner" in people else 0.0

    # Create perturbed situation
    perturbed = copy.deepcopy(situation)
    perturbed["people"]["you"]["employment_income"] = {year: pwages + DELTA * p_share}
    if "your partner" in perturbed["people"]:
        perturbed["people"]["your partner"]["employment_income"] = {
            year: swages + DELTA * s_share
        }

    # Run perturbed simulation
    perturbed_sim = Simulation(situation=perturbed)
    if disable_salt:
        perturbed_sim.set_input(
            variable_name="state_and_local_sales_or_income_tax",
            value=0.0,
            period=year,
        )

    new_federal = float(
        perturbed_sim.calculate("income_tax", period=year)[0]
    ) + float(perturbed_sim.calculate("additional_medicare_tax", period=year)[0])
    new_state = float(perturbed_sim.calculate("state_income_tax", period=year)[0])

    return {
        "frate": round(100.0 * (new_federal - base_federal) / DELTA, 4),
        "srate": round(100.0 * (new_state - base_state) / DELTA, 4),
    }
