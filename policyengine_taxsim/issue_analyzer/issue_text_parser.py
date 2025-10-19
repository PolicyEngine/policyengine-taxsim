"""Parse TaxAct values from issue description text when PDFs don't have form fields."""

import re
from typing import Dict, Optional


class IssueTextParser:
    """Extracts TaxAct values mentioned in issue descriptions."""

    def __init__(self, issue_text: str):
        self.issue_text = issue_text

    def extract_taxact_values(self) -> Dict[str, float]:
        """
        Extract TaxAct values from issue text.

        Looks for patterns like:
        - "TA shows a marriage credit of 144"
        - "TaxAct shows 144"
        - "TaxAct: $144"
        """
        values = {}

        # Pattern: "TA shows [variable] of [number]"
        pattern1 = r'TA shows (?:a |an )?([a-z\s]+?)(?:of |:)\s*\$?(\d+(?:\.\d+)?)'
        matches = re.findall(pattern1, self.issue_text, re.IGNORECASE)

        for variable, value in matches:
            variable = variable.strip().replace(' ', '_')
            values[variable] = float(value)

        # Pattern: "TaxAct shows [variable] of [number]"
        pattern2 = r'TaxAct shows (?:a |an )?([a-z\s]+?)(?:of |:)\s*\$?(\d+(?:\.\d+)?)'
        matches = re.findall(pattern2, self.issue_text, re.IGNORECASE)

        for variable, value in matches:
            variable = variable.strip().replace(' ', '_')
            values[variable] = float(value)

        # Pattern: Variable mentioned with value in context
        # "marriage credit of 144"
        pattern3 = r'([a-z\s]+?credit|[a-z\s]+?tax|[a-z\s]+?deduction|AGI|income)\s+(?:of |is |=)\s*\$?(\d+(?:\.\d+)?)'
        matches = re.findall(pattern3, self.issue_text, re.IGNORECASE)

        for variable, value in matches:
            variable = variable.strip().replace(' ', '_')
            if variable not in values:  # Don't overwrite more specific matches
                values[variable] = float(value)

        return values

    def extract_pe_vs_taxact_comparison(self) -> Optional[Dict]:
        """
        Extract direct comparisons like "TA shows 144 while PE shows 247"

        Returns dict with variable, taxact_value, pe_value
        """
        # Pattern: "TA shows [variable] of X while PE shows Y"
        pattern = r'TA shows (?:a |an )?([a-z\s]+?)of\s+(\d+)\s+while\s+PE shows\s+(\d+)'
        match = re.search(pattern, self.issue_text, re.IGNORECASE)

        if match:
            variable = match.group(1).strip().replace(' ', '_')
            return {
                'variable': variable,
                'taxact_value': float(match.group(2)),
                'pe_value': float(match.group(3))
            }

        # Alternative pattern: "TA: X, PE: Y"
        pattern2 = r'TA:?\s*\$?(\d+(?:\.\d+)?)[,;]?\s+(?:while\s+)?PE:?\s*\$?(\d+(?:\.\d+)?)'
        match = re.search(pattern2, self.issue_text, re.IGNORECASE)

        if match:
            return {
                'variable': 'unknown',
                'taxact_value': float(match.group(1)),
                'pe_value': float(match.group(2))
            }

        return None

    def parse_all(self) -> Dict[str, float]:
        """Parse all available TaxAct values from issue text."""
        values = self.extract_taxact_values()

        # Also try to get comparison
        comparison = self.extract_pe_vs_taxact_comparison()
        if comparison and comparison['variable'] != 'unknown':
            values[comparison['variable']] = comparison['taxact_value']

        return values
