"""Finds and categorizes discrepancies between TaxAct and PolicyEngine."""

from typing import Dict, List, Optional


class DiscrepancyFinder:
    """Compares TaxAct and PolicyEngine values to find discrepancies."""

    # Mapping of common variable names between systems
    VARIABLE_MAPPINGS = {
        # Federal
        'adjusted_gross_income': ['federal_agi', 'agi'],
        'taxable_income': ['federal_taxable_income'],
        'total_tax': ['federal_income_tax'],
        'self_employment_tax': ['fica'],
        'child_tax_credit': ['child_tax_credit'],
        'earned_income_credit': ['earned_income_credit', 'eitc'],

        # State - Minnesota specific
        'mn_taxable_income': ['state_taxable_income'],
        'marriage_credit': ['state_total_credits', 'mn_marriage_credit'],
        'total_credits': ['state_total_credits'],
    }

    def __init__(self, tolerance: float = 15.0):
        """
        Initialize discrepancy finder.

        Args:
            tolerance: Dollar amount tolerance for matching (default $15)
        """
        self.tolerance = tolerance

    def find_discrepancies(
        self,
        taxact_values: Dict[str, float],
        pe_values: Dict[str, float]
    ) -> List[Dict]:
        """
        Find all discrepancies between TaxAct and PolicyEngine.

        Returns:
            List of discrepancy dicts with variable, taxact_value, pe_value, difference
        """
        discrepancies = []

        # Try to match variables
        matched_pairs = self._match_variables(taxact_values, pe_values)

        for taxact_var, pe_var in matched_pairs.items():
            taxact_val = taxact_values.get(taxact_var, 0)
            pe_val = pe_values.get(pe_var, 0)

            difference = abs(taxact_val - pe_val)

            if difference > self.tolerance:
                discrepancies.append({
                    'variable': taxact_var,
                    'taxact_variable': taxact_var,
                    'pe_variable': pe_var,
                    'taxact_value': taxact_val,
                    'pe_value': pe_val,
                    'difference': difference,
                    'tolerance': self.tolerance
                })

        return discrepancies

    def _match_variables(
        self,
        taxact_values: Dict[str, float],
        pe_values: Dict[str, float]
    ) -> Dict[str, str]:
        """
        Match TaxAct variable names to PolicyEngine variable names.

        Returns:
            Dict mapping taxact_var -> pe_var
        """
        matched = {}

        # Direct matches (same name)
        for taxact_var in taxact_values.keys():
            if taxact_var in pe_values:
                matched[taxact_var] = taxact_var

        # Use mapping dictionary
        for canonical_name, variant_names in self.VARIABLE_MAPPINGS.items():
            taxact_var = None
            pe_var = None

            # Check if canonical name or any variant matches TaxAct
            for ta_var in taxact_values.keys():
                if ta_var == canonical_name or ta_var in variant_names:
                    taxact_var = ta_var
                    break

            # Check if canonical name or any variant matches PE
            for variant in variant_names:
                if variant in pe_values:
                    pe_var = variant
                    break

            if taxact_var and pe_var:
                matched[taxact_var] = pe_var

        return matched

    def categorize_discrepancies(
        self,
        discrepancies: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Categorize discrepancies by type (federal, state, credits, etc.).
        """
        categories = {
            'federal_income': [],
            'state_income': [],
            'credits': [],
            'deductions': [],
            'other': []
        }

        for disc in discrepancies:
            var = disc['variable'].lower()

            if 'credit' in var:
                categories['credits'].append(disc)
            elif 'deduction' in var:
                categories['deductions'].append(disc)
            elif 'state' in var or 'mn_' in var or 'ca_' in var:
                categories['state_income'].append(disc)
            elif 'federal' in var or 'agi' in var or 'taxable_income' in var:
                categories['federal_income'].append(disc)
            else:
                categories['other'].append(disc)

        return categories

    def prioritize_discrepancies(
        self,
        discrepancies: List[Dict]
    ) -> List[Dict]:
        """
        Sort discrepancies by importance/magnitude.

        Larger differences and tax liabilities prioritized over credits.
        """
        def priority_score(disc):
            # Higher difference = higher priority
            score = disc['difference']

            # Boost priority for main tax calculations
            var = disc['variable'].lower()
            if 'tax' in var and 'credit' not in var:
                score *= 2
            elif 'agi' in var or 'taxable_income' in var:
                score *= 1.5

            return score

        return sorted(discrepancies, key=priority_score, reverse=True)
