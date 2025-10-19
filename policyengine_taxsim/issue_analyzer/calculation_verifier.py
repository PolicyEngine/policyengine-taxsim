"""Automatically verifies tax calculations by reading and executing PolicyEngine code."""

from pathlib import Path
from typing import Dict, Optional, Tuple
import re
import yaml


class CalculationVerifier:
    """Verifies tax calculations by reading PolicyEngine code and parameters."""

    def __init__(self, policyengine_us_path: Optional[Path] = None):
        """
        Initialize verifier.

        Args:
            policyengine_us_path: Path to policyengine-us repo.
                                  If None, tries to find it relative to policyengine-taxsim
        """
        if policyengine_us_path:
            self.pe_us_path = Path(policyengine_us_path)
        else:
            # Try to find policyengine-us as sibling directory
            taxsim_path = Path(__file__).parent.parent.parent
            self.pe_us_path = taxsim_path.parent / "policyengine-us"

            if not self.pe_us_path.exists():
                # Try current working directory
                import os
                cwd = Path(os.getcwd())
                candidates = [
                    cwd.parent / "policyengine-us",
                    cwd / "policyengine-us",
                    Path.home() / "policyengine-us"
                ]
                for candidate in candidates:
                    if candidate.exists():
                        self.pe_us_path = candidate
                        break

        self.variables_path = self.pe_us_path / "policyengine_us" / "variables"
        self.parameters_path = self.pe_us_path / "policyengine_us" / "parameters"

    def verify_discrepancy(
        self,
        discrepancy: Dict,
        input_data: Dict,
        issue_context: str = ""
    ) -> Dict:
        """
        Find PolicyEngine code and parameters for a variable.

        Returns code/parameters that can be passed to LLM for analysis.
        This is now a CODE FINDER, not a calculator.
        """
        variable = discrepancy['variable']

        # Try to find the variable implementation
        code_info = self._find_variable_code(variable)

        if not code_info:
            return {
                'verified': False,
                'verdict': 'Unknown',
                'explanation': f"Could not find PolicyEngine code for variable: {variable}",
                'needs_llm': True
            }

        # Find parameters referenced in the code
        parameters_info = self._find_parameters_for_variable(code_info)

        # Return code + parameters for LLM to analyze
        return {
            'verified': False,  # We don't calculate ourselves anymore
            'code_found': True,
            'code_location': code_info['file_path'],
            'code': code_info['code'],
            'parameters': parameters_info,
            'explanation': f"Found PolicyEngine code at {code_info['file_path']}",
            'needs_llm': True  # Always pass to LLM for actual calculation
        }

    def _find_variable_code(self, variable_name: str) -> Optional[Dict]:
        """
        Find the PolicyEngine variable implementation.

        Returns dict with 'file_path', 'code', 'class_name'
        """
        # Common variable name mappings
        pe_var_names = [
            variable_name,
            variable_name.replace('_credit', ''),
            f"mn_{variable_name}",
            variable_name.replace('marriage', 'mn_marriage')
        ]

        for var_name in pe_var_names:
            # Try to find the file
            # Search in state directories
            for state_dir in ['mn', 'ca', 'ny', 'tx']:  # Add more as needed
                search_path = self.variables_path / "gov" / "states" / state_dir
                if search_path.exists():
                    for py_file in search_path.rglob("*.py"):
                        content = py_file.read_text()
                        if f"class {var_name}(" in content:
                            return {
                                'file_path': str(py_file),
                                'code': content,
                                'class_name': var_name,
                                'variable_name': var_name
                            }

        return None

    def _find_parameters_for_variable(self, code_info: Dict) -> Dict:
        """
        Find parameter files referenced in the variable code.

        Looks for patterns like:
        - parameters(period).gov.states.mn.tax.income.credits.marriage
        - p.maximum_amount
        """
        import re

        code = code_info['code']
        parameters = {}

        # Find parameter paths in code (e.g., parameters(period).gov.states.mn...)
        param_pattern = r'parameters\(period\)\.([a-z_\.]+)'
        matches = re.findall(param_pattern, code)

        for match in matches:
            # Convert dot notation to file path
            # gov.states.mn.tax.income → gov/states/mn/tax/income
            param_path = match.replace('.', '/')
            full_path = self.parameters_path / f"{param_path}.yaml"

            if full_path.exists():
                parameters[match] = {
                    'path': str(full_path),
                    'content': full_path.read_text()
                }
            else:
                # Try as directory - recursively read YAML files
                dir_path = self.parameters_path / param_path
                if dir_path.exists() and dir_path.is_dir():
                    # Recursively read all YAML files
                    for yaml_file in dir_path.rglob('*.yaml'):
                        rel_path = yaml_file.relative_to(self.parameters_path)
                        key = str(rel_path).replace('/', '.').replace('.yaml', '')
                        parameters[key] = {
                            'path': str(yaml_file),
                            'note': f'Parameter found via {match}'
                        }

        return parameters

    def _verify_mn_marriage_credit(
        self,
        taxact_value: float,
        pe_value: float,
        input_data: Dict,
        code_info: Dict
    ) -> Dict:
        """Verify Minnesota marriage credit calculation."""

        try:
            # Read parameters
            params = self._read_mn_marriage_credit_params()

            # Calculate expected value
            calculation = self._calculate_mn_marriage_credit(input_data, params)

            if not calculation['success']:
                return {
                    'verified': False,
                    'verdict': 'Unknown',
                    'explanation': calculation['error'],
                    'needs_llm': True
                }

            calculated = calculation['credit']
            steps = calculation['steps']

            # Determine verdict (use $1 tolerance for rounding)
            tolerance = 1.0
            pe_matches = abs(calculated - pe_value) < tolerance
            taxact_matches = abs(calculated - taxact_value) < tolerance

            if pe_matches and not taxact_matches:
                verdict = "PolicyEngine is correct"
                explanation = f"Manual calculation yields ${calculated:.2f}, matching PolicyEngine's ${pe_value:.2f}. TaxAct's ${taxact_value:.2f} is incorrect."
            elif taxact_matches and not pe_matches:
                verdict = "TaxAct is correct"
                explanation = f"Manual calculation yields ${calculated:.2f}, matching TaxAct's ${taxact_value:.2f}. PolicyEngine's ${pe_value:.2f} is incorrect."
            elif pe_matches and taxact_matches:
                verdict = "Both are correct"
                explanation = f"Both TaxAct (${taxact_value:.2f}) and PolicyEngine (${pe_value:.2f}) match the calculated value ${calculated:.2f}."
            else:
                verdict = "Both are incorrect"
                explanation = f"Manual calculation yields ${calculated:.2f}, which matches neither TaxAct (${taxact_value:.2f}) nor PolicyEngine (${pe_value:.2f})."

            # Remove parameters_used to avoid JSON serialization issues with dates
            return {
                'verified': True,
                'verdict': verdict,
                'calculated_value': calculated,
                'explanation': explanation,
                'calculation_steps': steps,
                'needs_llm': False
            }

        except Exception as e:
            return {
                'verified': False,
                'verdict': 'Unknown',
                'explanation': f"Error during calculation: {str(e)}",
                'needs_llm': True
            }

    def _read_mn_marriage_credit_params(self) -> Dict:
        """Read Minnesota marriage credit parameters for 2024."""
        from datetime import date

        base_path = self.parameters_path / "gov" / "states" / "mn" / "tax" / "income" / "credits" / "marriage"

        params = {}

        # Read each parameter file
        param_files = {
            'maximum_amount': 'maximum_amount.yaml',
            'minimum_individual_income': 'minimum_individual_income.yaml',
            'minimum_taxable_income': 'minimum_taxable_income.yaml',
            'standard_deduction_fraction': 'standard_deduction_fraction.yaml'
        }

        for key, filename in param_files.items():
            file_path = base_path / filename
            if file_path.exists():
                with open(file_path) as f:
                    data = yaml.safe_load(f)
                    # Get 2024 value (or latest) - handle both string and datetime.date keys
                    values = data.get('values', {})
                    params[key] = (values.get(date(2024, 1, 1)) or
                                  values.get('2024-01-01') or
                                  values.get(date(2021, 1, 1)) or
                                  values.get('2021-01-01'))

        # Read standard deduction
        std_ded_path = self.parameters_path / "gov" / "states" / "mn" / "tax" / "income" / "deductions" / "standard" / "base.yaml"
        if std_ded_path.exists():
            with open(std_ded_path) as f:
                data = yaml.safe_load(f)
                joint_values = data.get('JOINT', {}).get('values', {})
                params['standard_deduction_joint'] = (joint_values.get(date(2024, 1, 1)) or
                                                      joint_values.get('2024-01-01') or 29150)

        # Read tax rates
        rates_path = self.parameters_path / "gov" / "states" / "mn" / "tax" / "income" / "rates"

        # Single rates
        single_file = rates_path / "single.yaml"
        if single_file.exists():
            with open(single_file) as f:
                data = yaml.safe_load(f)
                params['single_brackets'] = data.get('brackets', [])

        # Joint rates
        joint_file = rates_path / "joint.yaml"
        if joint_file.exists():
            with open(joint_file) as f:
                data = yaml.safe_load(f)
                params['joint_brackets'] = data.get('brackets', [])

        return params

    def _calculate_mn_marriage_credit(self, input_data: Dict, params: Dict) -> Dict:
        """
        Calculate Minnesota marriage credit from input data.

        Returns dict with 'success', 'credit', 'steps', or 'error'
        """
        steps = []

        try:
            # Get inputs - try multiple keys
            primary_se = input_data.get('psemp', input_data.get('primary_se_income', 0))
            spouse_se = input_data.get('ssemp', input_data.get('spouse_se_income', 0))
            mn_taxable_income = input_data.get('mn_taxable_income', input_data.get('state_taxable_income', 0))

            steps.append(f"Primary SE income: ${primary_se:,.2f}")
            steps.append(f"Spouse SE income: ${spouse_se:,.2f}")
            steps.append(f"MN taxable income: ${mn_taxable_income:,.2f}")

            # Calculate SE tax deduction (simplified - 50% of SE tax)
            # Full calculation: SE tax = (SE income * 0.9235 * 0.153) for both OASDI and Medicare
            # Deduction = 50% of that
            se_tax_rate = 0.153
            primary_se_tax = primary_se * 0.9235 * se_tax_rate
            spouse_se_tax = spouse_se * 0.9235 * se_tax_rate

            primary_se_deduction = primary_se_tax / 2
            spouse_se_deduction = spouse_se_tax / 2

            steps.append(f"Primary SE tax deduction: ${primary_se_deduction:,.2f}")
            steps.append(f"Spouse SE tax deduction: ${spouse_se_deduction:,.2f}")

            # Calculate individual incomes for credit purposes
            primary_income = primary_se - primary_se_deduction
            spouse_income = spouse_se - spouse_se_deduction
            min_income = min(primary_income, spouse_income)

            steps.append(f"Primary income (after SE deduction): ${primary_income:,.2f}")
            steps.append(f"Spouse income (after SE deduction): ${spouse_income:,.2f}")
            steps.append(f"Minimum income: ${min_income:,.2f}")

            # Check eligibility
            min_individual = params.get('minimum_individual_income', 30000)
            min_taxable = params.get('minimum_taxable_income', 47000)

            if min_income < min_individual:
                steps.append(f"❌ Ineligible: min_income ${min_income:,.2f} < ${min_individual:,.2f}")
                return {'success': True, 'credit': 0.0, 'steps': steps}

            if mn_taxable_income < min_taxable:
                steps.append(f"❌ Ineligible: mn_taxable_income ${mn_taxable_income:,.2f} < ${min_taxable:,.2f}")
                return {'success': True, 'credit': 0.0, 'steps': steps}

            steps.append(f"✓ Eligible: min_income >= ${min_individual:,.2f} and mn_taxable_income >= ${min_taxable:,.2f}")

            # Calculate credit
            std_ded = params.get('standard_deduction_joint', 29150)
            frac = params.get('standard_deduction_fraction', 0.5)
            fractional_std_ded = frac * std_ded

            steps.append(f"Standard deduction: ${std_ded:,.2f}")
            steps.append(f"Fractional std ded (50%): ${fractional_std_ded:,.2f}")

            taxinc1 = max(0, min_income - fractional_std_ded)
            steps.append(f"Taxinc1 = max(0, ${min_income:,.2f} - ${fractional_std_ded:,.2f}) = ${taxinc1:,.2f}")

            # Calculate itax1 using single rates
            itax1 = self._apply_tax_brackets(taxinc1, params['single_brackets'])
            steps.append(f"Itax1 (single rate on ${taxinc1:,.2f}): ${itax1:,.2f}")

            # Calculate taxinc2
            taxinc2 = max(0, mn_taxable_income - taxinc1)
            steps.append(f"Taxinc2 = max(0, ${mn_taxable_income:,.2f} - ${taxinc1:,.2f}) = ${taxinc2:,.2f}")

            # Calculate itax2 using single rates
            itax2 = self._apply_tax_brackets(taxinc2, params['single_brackets'])
            steps.append(f"Itax2 (single rate on ${taxinc2:,.2f}): ${itax2:,.2f}")

            # Calculate itax0 using joint rates
            itax0 = self._apply_tax_brackets(mn_taxable_income, params['joint_brackets'])
            steps.append(f"Itax0 (joint rate on ${mn_taxable_income:,.2f}): ${itax0:,.2f}")

            # Calculate credit
            credit_uncapped = max(0, itax0 - itax1 - itax2)
            steps.append(f"Credit (uncapped) = max(0, ${itax0:,.2f} - ${itax1:,.2f} - ${itax2:,.2f}) = ${credit_uncapped:,.2f}")

            # Cap at maximum
            max_credit = params.get('maximum_amount', 1801)
            credit = min(credit_uncapped, max_credit)
            steps.append(f"Final credit = min(${credit_uncapped:,.2f}, ${max_credit:,.2f}) = ${credit:,.2f}")

            return {
                'success': True,
                'credit': credit,
                'steps': steps
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"Calculation error: {str(e)}",
                'steps': steps
            }

    def _apply_tax_brackets(self, income: float, brackets: list) -> float:
        """Apply tax brackets to calculate tax."""
        from datetime import date

        # Get 2024 values from brackets and build a simple bracket list
        simple_brackets = []
        for bracket in brackets:
            threshold_data = bracket.get('threshold', {})
            rate_data = bracket.get('rate', {})

            # Get 2024 threshold - handle both string and datetime.date keys
            threshold = 0
            if isinstance(threshold_data, dict):
                if 'values' in threshold_data:
                    # Try datetime.date first, then string
                    values_dict = threshold_data['values']
                    threshold = (values_dict.get(date(2024, 1, 1)) or
                                values_dict.get('2024-01-01') or
                                values_dict.get(date(2021, 1, 1)) or
                                values_dict.get('2021-01-01') or 0)
                else:
                    threshold = (threshold_data.get(date(2024, 1, 1)) or
                                threshold_data.get('2024-01-01') or
                                threshold_data.get(date(2021, 1, 1)) or
                                threshold_data.get('2021-01-01') or 0)
            else:
                threshold = threshold_data

            # Get 2024 rate - handle both string and datetime.date keys
            rate = 0
            if isinstance(rate_data, dict):
                rate = (rate_data.get(date(2024, 1, 1)) or
                       rate_data.get('2024-01-01') or
                       rate_data.get(date(2021, 1, 1)) or
                       rate_data.get('2021-01-01') or 0)
            else:
                rate = rate_data

            simple_brackets.append((float(threshold), float(rate)))

        # Sort by threshold
        simple_brackets.sort(key=lambda x: x[0])

        # Apply brackets using standard tax calculation
        tax = 0.0
        for i, (threshold, rate) in enumerate(simple_brackets):
            if income <= threshold:
                # Income doesn't reach this bracket
                break

            # Find the next threshold (or use income if this is the last bracket)
            if i < len(simple_brackets) - 1:
                next_threshold = simple_brackets[i + 1][0]
            else:
                next_threshold = float('inf')

            # Calculate taxable amount in this bracket
            taxable_in_bracket = min(income, next_threshold) - threshold

            # Add tax from this bracket
            tax += taxable_in_bracket * rate

        return tax
