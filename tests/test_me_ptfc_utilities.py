"""Maine property tax fairness credit: rentpaid is treated as gross rent that
includes heat/utilities, so the emulator flags utilities_included_in_rent for
Maine records with rent. This is scoped to Maine because the same variable also
feeds Michigan's home heating credit. See taxsim issue #1126.
"""

from policyengine_taxsim.core.input_mapper import form_household_situation


def _record(state, rentpaid):
    return {
        "taxsimid": 1,
        "year": 2022,
        "state": state,
        "mstat": 1,
        "page": 49,
        "depx": 1,
        "pwages": 44452.57,
        "rentpaid": rentpaid,
    }


def test_maine_rent_sets_utilities_included_in_rent():
    situation = form_household_situation(2022, "ME", _record(20, 17139.244))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert tax_unit["utilities_included_in_rent"] == {"2022": True}


def test_maine_without_rent_does_not_set_flag():
    situation = form_household_situation(2022, "ME", _record(20, 0))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit


def test_michigan_rent_does_not_set_flag():
    # utilities_included_in_rent also feeds Michigan's home heating credit, so
    # the Maine flag must not leak to other states.
    situation = form_household_situation(2022, "MI", _record(24, 17139.244))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit
