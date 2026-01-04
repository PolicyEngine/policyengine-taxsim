"""Parser for extracting values from TaxAct PDF forms."""

from pathlib import Path
from typing import Dict, Optional, List
import pypdf


class TaxActPDFParser:
    """Extracts tax values from TaxAct-filled PDF forms."""

    # Common form field mappings (will expand as we encounter more)
    FORM_FIELD_MAPPINGS = {
        # Federal Form 1040
        '1040': {
            'f1_01': 'wages',
            'f1_11': 'adjusted_gross_income',
            'f1_15': 'taxable_income',
            'f1_24': 'total_tax',
        },
        # Schedule SE (Self-Employment)
        'Schedule SE': {
            'f1_04': 'self_employment_income',
            'f1_10': 'self_employment_tax',
            'f1_13': 'deductible_se_tax',
        },
        # Minnesota Form M1
        'M1': {
            'f1_01': 'federal_agi',
            'f1_15': 'mn_taxable_income',
            'f1_19': 'mn_tax_before_credits',
        },
        # Minnesota Schedule M1C (Credits)
        'M1C': {
            'f1_05': 'marriage_credit',
            'f1_10': 'dependent_care_credit',
            'f1_20': 'k12_education_credit',
        }
    }

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.reader = None
        self.form_type = self._detect_form_type()

    def _detect_form_type(self) -> Optional[str]:
        """Detect the type of tax form from filename."""
        filename = self.pdf_path.name.lower()

        if '1040' in filename and 'schedule' not in filename:
            return '1040'
        elif 'schedule se' in filename or 'schedule_se' in filename:
            return 'Schedule SE'
        elif 'form m1' in filename or 'form_m1' in filename:
            if 'm1c' not in filename:
                return 'M1'
        elif 'm1c' in filename or 'schedule m1c' in filename:
            return 'M1C'

        return None

    def extract_form_fields(self) -> Dict[str, str]:
        """Extract all form fields and their values from the PDF."""
        try:
            self.reader = pypdf.PdfReader(self.pdf_path)

            if not self.reader.get_form_text_fields():
                return {}

            fields = self.reader.get_form_text_fields()
            return fields

        except Exception as e:
            print(f"Warning: Could not extract form fields from {self.pdf_path.name}: {e}")
            return {}

    def extract_values(self) -> Dict[str, float]:
        """Extract numeric values from form fields."""
        fields = self.extract_form_fields()

        values = {}

        # Get mapping for this form type
        mapping = self.FORM_FIELD_MAPPINGS.get(self.form_type, {})

        for field_name, field_value in fields.items():
            # Try to map to known tax concept
            if field_name in mapping:
                tax_concept = mapping[field_name]

                # Try to parse as number
                try:
                    # Clean the value (remove $, commas, etc.)
                    cleaned = str(field_value).replace('$', '').replace(',', '').strip()
                    if cleaned:
                        numeric_value = float(cleaned)
                        values[tax_concept] = numeric_value
                except (ValueError, AttributeError):
                    pass

        return values

    def extract_line_items(self) -> Dict[str, float]:
        """
        Alternative method: Extract values by line numbers.
        Useful when form field names are unclear.
        """
        # This would use OCR or text extraction
        # For now, return form fields
        return self.extract_values()


class TaxActPDFBatchParser:
    """Parse multiple TaxAct PDFs and combine results."""

    def __init__(self, pdf_paths: List[Path]):
        self.pdf_paths = pdf_paths

    def parse_all(self) -> Dict[str, Dict[str, float]]:
        """Parse all PDFs and organize by form type."""
        results = {}

        for pdf_path in self.pdf_paths:
            parser = TaxActPDFParser(pdf_path)
            form_type = parser.form_type

            if form_type:
                values = parser.extract_values()
                if values:
                    # Handle multiple forms of same type (e.g., two Schedule SE)
                    if form_type in results:
                        # Add suffix to distinguish
                        suffix = 1
                        while f"{form_type}_{suffix}" in results:
                            suffix += 1
                        form_type = f"{form_type}_{suffix}"

                    results[form_type] = values

        return results

    def get_consolidated_values(self) -> Dict[str, float]:
        """Get all values consolidated into a single dict."""
        all_forms = self.parse_all()

        consolidated = {}
        for form_type, values in all_forms.items():
            for key, value in values.items():
                # If key already exists, store with form prefix
                if key in consolidated:
                    consolidated[f"{form_type}_{key}"] = value
                else:
                    consolidated[key] = value

        return consolidated
