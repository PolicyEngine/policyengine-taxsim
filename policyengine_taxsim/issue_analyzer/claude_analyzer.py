"""Claude API integration for analyzing tax discrepancies."""

import os
import json
from typing import Dict, Optional, List
from anthropic import Anthropic


class ClaudeAnalyzer:
    """Uses Claude API to analyze tax discrepancies and suggest fixes."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

    def analyze_discrepancy(
        self,
        discrepancy: Dict,
        issue_context: str,
        pe_code: Optional[str] = None,
        tax_law_refs: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze a single discrepancy and suggest fixes.

        Args:
            discrepancy: Dict with 'variable', 'taxact_value', 'pe_value', 'difference'
            issue_context: Original issue description from GitHub
            pe_code: Relevant PolicyEngine code (if found)
            tax_law_refs: List of tax law document URLs

        Returns:
            Dict with analysis results including suggested fix
        """
        prompt = self._build_analysis_prompt(
            discrepancy, issue_context, pe_code, tax_law_refs
        )

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text

            # Parse the response
            analysis = self._parse_analysis_response(response_text, discrepancy)

            return analysis

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return {
                'error': str(e),
                'variable': discrepancy['variable'],
                'analysis_attempted': True
            }

    def _build_analysis_prompt(
        self,
        discrepancy: Dict,
        issue_context: str,
        pe_code: Optional[str],
        tax_law_refs: Optional[List[str]]
    ) -> str:
        """Build the prompt for Claude to analyze the discrepancy."""

        prompt = f"""You are a tax calculation expert analyzing a discrepancy between TaxAct (commercial tax software) and PolicyEngine (open-source tax calculator).

## Issue Context
{issue_context}

## Discrepancy Found

**Variable:** {discrepancy['variable']}
**TaxAct Value:** ${discrepancy['taxact_value']:,.2f}
**PolicyEngine Value:** ${discrepancy['pe_value']:,.2f}
**Difference:** ${discrepancy['difference']:,.2f}

## Input Data
{json.dumps(discrepancy.get('input_data', {}), indent=2)}
"""

        if pe_code:
            prompt += f"""

## PolicyEngine Implementation

```python
{pe_code}
```
"""

        if tax_law_refs:
            prompt += f"""

## Tax Law References
{chr(10).join(f"- {ref}" for ref in tax_law_refs)}
"""

        prompt += """

## Your Task

Please analyze this discrepancy and provide:

1. **Which is correct?** TaxAct or PolicyEngine? Explain your reasoning.

2. **Root cause:** What is causing the discrepancy? Be specific about the calculation error.

3. **Fix needed:** If PolicyEngine is wrong, provide:
   - The specific line(s) of code that need to change
   - The corrected implementation
   - Why this fix resolves the issue

4. **If TaxAct is wrong:** Explain why TaxAct might be incorrect and PolicyEngine is right.

5. **Answer any specific questions** from the issue context above.

Format your response as:

**VERDICT:** [TaxAct is correct | PolicyEngine is correct | Both have issues | Need more information]

**EXPLANATION:**
[Your detailed analysis]

**ROOT CAUSE:**
[Specific cause of the discrepancy]

**RECOMMENDED FIX:**
```python
# If PolicyEngine needs fixing, provide the corrected code here
# Include context about which file and function to modify
```

**TAX LAW JUSTIFICATION:**
[Reference to specific tax law, form instructions, or regulations]
"""

        return prompt

    def _parse_analysis_response(self, response_text: str, discrepancy: Dict) -> Dict:
        """Parse Claude's response into structured data."""

        # Extract verdict
        verdict = "Unknown"
        if "TaxAct is correct" in response_text or "VERDICT:** TaxAct is correct" in response_text:
            verdict = "TaxAct is correct"
        elif "PolicyEngine is correct" in response_text or "VERDICT:** PolicyEngine is correct" in response_text:
            verdict = "PolicyEngine is correct"
        elif "Both have issues" in response_text:
            verdict = "Both have issues"
        elif "Need more information" in response_text:
            verdict = "Need more information"

        # Extract code fix if present
        import re
        code_pattern = r'```python\n(.*?)\n```'
        code_matches = re.findall(code_pattern, response_text, re.DOTALL)
        suggested_fix = code_matches[0] if code_matches else None

        return {
            'variable': discrepancy['variable'],
            'verdict': verdict,
            'full_analysis': response_text,
            'suggested_fix': suggested_fix,
            'taxact_value': discrepancy['taxact_value'],
            'pe_value': discrepancy['pe_value'],
            'difference': discrepancy['difference'],
        }

    def analyze_multiple_discrepancies(
        self,
        discrepancies: List[Dict],
        issue_context: str,
        pe_code_map: Optional[Dict[str, str]] = None,
        tax_law_refs: Optional[List[str]] = None
    ) -> List[Dict]:
        """Analyze multiple discrepancies."""

        results = []

        for i, discrepancy in enumerate(discrepancies, 1):
            print(f"🤖 Analyzing discrepancy {i}/{len(discrepancies)}: {discrepancy['variable']}...")

            pe_code = None
            if pe_code_map and discrepancy['variable'] in pe_code_map:
                pe_code = pe_code_map[discrepancy['variable']]

            analysis = self.analyze_discrepancy(
                discrepancy, issue_context, pe_code, tax_law_refs
            )

            results.append(analysis)

        return results
