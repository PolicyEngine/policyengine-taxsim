"""Main analyzer orchestrating the complete issue analysis workflow."""

from pathlib import Path
from typing import Dict, Optional
import json

try:
    from .taxsim_fetcher import TaxsimNberOrgFetcher, extract_taxsim_url_from_issue
    from .pdf_parser import TaxActPDFBatchParser
    from .pe_output_parser import PolicyEngineOutputParser
    from .discrepancy_finder import DiscrepancyFinder
    from .claude_analyzer import ClaudeAnalyzer
    from .github_fetcher import GitHubIssueFetcher
    from .issue_text_parser import IssueTextParser
    from .calculation_verifier import CalculationVerifier
except ImportError:
    from policyengine_taxsim.issue_analyzer.taxsim_fetcher import TaxsimNberOrgFetcher, extract_taxsim_url_from_issue
    from policyengine_taxsim.issue_analyzer.pdf_parser import TaxActPDFBatchParser
    from policyengine_taxsim.issue_analyzer.pe_output_parser import PolicyEngineOutputParser
    from policyengine_taxsim.issue_analyzer.discrepancy_finder import DiscrepancyFinder
    from policyengine_taxsim.issue_analyzer.claude_analyzer import ClaudeAnalyzer
    from policyengine_taxsim.issue_analyzer.github_fetcher import GitHubIssueFetcher
    from policyengine_taxsim.issue_analyzer.issue_text_parser import IssueTextParser
    from policyengine_taxsim.issue_analyzer.calculation_verifier import CalculationVerifier


class IssueAnalyzer:
    """Orchestrates the complete issue analysis workflow."""

    def __init__(self, issue_number: int, output_dir: Optional[Path] = None, use_llm: bool = False):
        self.issue_number = issue_number
        self.output_dir = output_dir or Path(f'./issue_analysis_{issue_number}')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_llm = use_llm

        # Subdirectories
        self.attachments_dir = self.output_dir / 'attachments'
        self.results_dir = self.output_dir / 'results'

    def analyze(self) -> Dict:
        """Run complete analysis workflow."""
        print(f"{'='*60}")
        print(f"  Issue Analysis for #{self.issue_number}")
        print(f"{'='*60}\n")

        results = {}

        # Step 1: Fetch GitHub issue to get context and taxsim URL
        print("📥 Step 1: Fetching GitHub issue...")
        issue_data = self._fetch_github_issue()
        results['issue_data'] = issue_data

        # Step 2: Download from taxsim.nber.org
        print("\n📥 Step 2: Downloading from taxsim.nber.org...")
        taxsim_files = self._download_taxsim_files()
        results['taxsim_files'] = taxsim_files

        # Step 3: Parse TaxAct PDFs
        print("\n🔍 Step 3: Parsing TaxAct PDFs...")
        taxact_values = self._parse_taxact_pdfs(taxsim_files)

        # Fallback: Parse issue text if PDFs yielded no values
        if not taxact_values:
            print("   💡 Attempting to extract TaxAct values from issue description...")
            text_parser = IssueTextParser(issue_data['body'])
            taxact_values = text_parser.parse_all()
            if taxact_values:
                print(f"   ✓ Extracted {len(taxact_values)} values from issue text")
            else:
                print("   ⚠️  No TaxAct values found in issue text either")

        results['taxact_values'] = taxact_values

        # Step 4: Parse PolicyEngine output
        print("\n🔍 Step 4: Parsing PolicyEngine output...")
        pe_values = self._parse_pe_output(taxsim_files)
        results['pe_values'] = pe_values

        # Step 5: Find discrepancies
        print("\n⚖️  Step 5: Finding discrepancies...")
        discrepancies = self._find_discrepancies(taxact_values, pe_values)
        results['discrepancies'] = discrepancies

        if not discrepancies:
            print("✅ No discrepancies found! TaxAct and PolicyEngine match.")
            self._save_results(results)
            return results

        print(f"\n⚠️  Found {len(discrepancies)} discrepancy(ies)\n")
        for i, disc in enumerate(discrepancies, 1):
            print(f"{i}. {disc['variable']}")
            print(f"   TaxAct:       ${disc['taxact_value']:,.2f}")
            print(f"   PolicyEngine: ${disc['pe_value']:,.2f}")
            print(f"   Difference:   ${disc['difference']:,.2f}\n")

        # Step 6: Find PolicyEngine code and parameters
        print("🔍 Step 6: Finding PolicyEngine code...")
        input_data = self._extract_input_data(taxsim_files)
        code_findings = self._find_code_for_discrepancies(discrepancies, input_data, pe_values, issue_data)
        results['code_findings'] = code_findings

        # Print what we found
        for finding in code_findings:
            if finding.get('code_found'):
                print(f"\n✓ Found code: {finding['variable']}")
                print(f"   Location: {finding['code_location']}")
                print(f"   Parameters: {len(finding.get('parameters', {}))} files")
            else:
                print(f"\n⚠️  Code not found: {finding['variable']}")

        # Step 7: LLM Analysis (only if --use-llm flag or API key is set)
        import os
        has_api_key = bool(os.environ.get('ANTHROPIC_API_KEY'))

        if self.use_llm or has_api_key:
            print("🤖 Step 7: Running AI analysis with PolicyEngine code...")
            try:
                analyses = self._run_llm_analysis(discrepancies, issue_data, code_findings, input_data)
                results['analyses'] = analyses

                # Print verdicts
                print("\n📊 Analysis Results:\n")
                for analysis in analyses:
                    print(f"Variable: {analysis['variable']}")
                    print(f"Verdict: {analysis['verdict']}")
                    if analysis.get('suggested_fix'):
                        print(f"✓ Fix suggested")
                    print()
            except ValueError as e:
                if "ANTHROPIC_API_KEY" in str(e):
                    print(f"\n⚠️  Skipping AI analysis: {e}")
                    print("   Set ANTHROPIC_API_KEY or use --use-llm to enable AI analysis")
                else:
                    raise
        else:
            print("\n💡 Tip: Use --use-llm flag to run AI-powered analysis")

        # Step 8: Save results
        print("💾 Step 8: Saving results...")
        self._save_results(results)

        print(f"\n{'='*60}")
        print(f"✅ Analysis complete!")
        print(f"{'='*60}\n")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"📄 Results saved to: {self.results_dir / 'analysis_results.json'}")

        return results

    def _fetch_github_issue(self) -> Dict:
        """Fetch GitHub issue metadata."""
        fetcher = GitHubIssueFetcher()
        issue = fetcher.fetch_issue(self.issue_number)

        print(f"   ✓ Title: {issue['title']}")
        print(f"   ✓ Author: {issue['user']['login']}")

        return {
            'number': issue['number'],
            'title': issue['title'],
            'author': issue['user']['login'],
            'body': issue['body'],
            'url': issue['html_url']
        }

    def _download_taxsim_files(self) -> Dict:
        """Download files from taxsim.nber.org."""
        fetcher = TaxsimNberOrgFetcher(self.issue_number)

        # Download all files
        files = fetcher.download_all(self.attachments_dir)

        # Categorize
        categorized = fetcher.categorize_files(files)

        print(f"   ✓ Downloaded {len(files)} files")
        print(f"     - PDFs: {len(categorized['pdfs'])}")
        print(f"     - CSV: {len(categorized['csv'])}")
        print(f"     - TXT: {len(categorized['txt'])}")

        return categorized

    def _parse_taxact_pdfs(self, files: Dict) -> Dict[str, float]:
        """Parse TaxAct PDF forms."""
        if not files['pdfs']:
            print("   ⚠️  No PDFs found")
            return {}

        parser = TaxActPDFBatchParser(files['pdfs'])
        values = parser.get_consolidated_values()

        if values:
            print(f"   ✓ Extracted {len(values)} values from {len(files['pdfs'])} PDFs")
        else:
            print(f"   ⚠️  PDFs have no extractable form fields (may be flattened/images)")

        return values

    def _parse_pe_output(self, files: Dict) -> Dict[str, float]:
        """Parse PolicyEngine output.txt."""
        output_file = None
        for txt_file in files['txt']:
            if 'output' in txt_file.name.lower():
                output_file = txt_file
                break

        if not output_file:
            print("   ⚠️  No output.txt found")
            return {}

        parser = PolicyEngineOutputParser(output_file)
        values = parser.parse_all()

        print(f"   ✓ Extracted {len(values)} values from output.txt")

        return values

    def _find_discrepancies(
        self,
        taxact_values: Dict[str, float],
        pe_values: Dict[str, float]
    ) -> list:
        """Find discrepancies between TaxAct and PolicyEngine."""
        finder = DiscrepancyFinder(tolerance=15.0)
        discrepancies = finder.find_discrepancies(taxact_values, pe_values)

        # Prioritize
        discrepancies = finder.prioritize_discrepancies(discrepancies)

        return discrepancies

    def _run_llm_analysis(
        self,
        discrepancies: list,
        issue_data: Dict,
        code_findings: list,
        input_data: Dict
    ) -> list:
        """Run LLM analysis on discrepancies with PolicyEngine code."""
        analyzer = ClaudeAnalyzer()

        issue_context = f"""
Issue #{issue_data['number']}: {issue_data['title']}
Author: @{issue_data['author']}

{issue_data['body']}
"""

        # Build code map from findings
        pe_code_map = {}
        for finding in code_findings:
            if finding.get('code_found'):
                var = finding['variable']
                pe_code_map[var] = finding.get('code', '')
                # Also include parameters in context
                if finding.get('parameters'):
                    pe_code_map[var] += "\n\n# Parameters:\n"
                    for param_name, param_info in finding['parameters'].items():
                        pe_code_map[var] += f"\n## {param_name}\n```yaml\n{param_info['content']}\n```\n"

        analyses = analyzer.analyze_multiple_discrepancies(
            discrepancies,
            issue_context,
            pe_code_map=pe_code_map
        )

        return analyses

    def _extract_input_data(self, files: Dict) -> Dict:
        """Extract input data from CSV file."""
        input_data = {}

        # Find CSV file
        csv_file = None
        for csv in files.get('csv', []):
            csv_file = csv
            break

        if csv_file:
            import csv as csv_module
            with open(csv_file, 'r') as f:
                reader = csv_module.DictReader(f)
                for row in reader:
                    # Convert all values to floats where possible
                    for key, value in row.items():
                        try:
                            input_data[key] = float(value)
                        except (ValueError, TypeError):
                            input_data[key] = value
                    break  # Only get first row

        return input_data

    def _find_code_for_discrepancies(
        self,
        discrepancies: list,
        input_data: Dict,
        pe_values: Dict,
        issue_data: Dict
    ) -> list:
        """Find PolicyEngine code and parameters for each discrepancy."""
        verifier = CalculationVerifier()
        findings = []

        for disc in discrepancies:
            # Merge input data with PE values for calculations
            combined_data = {**input_data, **pe_values}

            finding = verifier.verify_discrepancy(
                disc,
                combined_data,
                issue_data.get('body', '')
            )
            finding['variable'] = disc['variable']
            finding['discrepancy'] = disc
            findings.append(finding)

        return findings

    def _save_results(self, results: Dict):
        """Save analysis results to files."""
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Save main results as JSON
        results_file = self.results_dir / 'analysis_results.json'

        # Prepare JSON-serializable version (exclude code content to keep file size small)
        code_findings = results.get('code_findings', [])
        code_findings_summary = []
        for finding in code_findings:
            summary = {
                'variable': finding.get('variable'),
                'code_found': finding.get('code_found', False),
                'code_location': finding.get('code_location'),
                'parameters_count': len(finding.get('parameters', {}))
            }
            code_findings_summary.append(summary)

        json_results = {
            'issue_number': self.issue_number,
            'issue_data': results.get('issue_data', {}),
            'taxact_values': results.get('taxact_values', {}),
            'pe_values': results.get('pe_values', {}),
            'discrepancies': results.get('discrepancies', []),
            'code_findings': code_findings_summary,
            'analyses': results.get('analyses', [])
        }

        # Convert datetime objects to strings for JSON serialization
        def json_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(results_file, 'w') as f:
            json.dump(json_results, f, indent=2, default=json_serializer)

        # Save a simple markdown summary
        summary_file = self.results_dir / 'SUMMARY.md'
        with open(summary_file, 'w') as f:
            f.write(self._generate_summary_markdown(json_results))

    def _generate_summary_markdown(self, results: Dict) -> str:
        """Generate a simple markdown summary."""
        md = f"# Analysis Summary - Issue #{self.issue_number}\n\n"

        issue_data = results.get('issue_data', {})
        md += f"**Title:** {issue_data.get('title', 'N/A')}\n"
        md += f"**Author:** @{issue_data.get('author', 'N/A')}\n\n"

        discrepancies = results.get('discrepancies', [])
        if not discrepancies:
            md += "✅ **No discrepancies found!**\n"
        else:
            md += f"## Discrepancies Found: {len(discrepancies)}\n\n"

            for i, disc in enumerate(discrepancies, 1):
                md += f"### {i}. {disc['variable']}\n\n"
                md += f"- **TaxAct:** ${disc['taxact_value']:,.2f}\n"
                md += f"- **PolicyEngine:** ${disc['pe_value']:,.2f}\n"
                md += f"- **Difference:** ${disc['difference']:,.2f}\n\n"

                # Add code location if found
                code_findings = results.get('code_findings', [])
                for finding in code_findings:
                    if finding.get('variable') == disc['variable'] and finding.get('code_found'):
                        md += f"**📁 PolicyEngine Code:** `{finding['code_location']}`\n\n"
                        break

                # Add AI analysis if available
                analyses = results.get('analyses', [])
                for analysis in analyses:
                    if analysis['variable'] == disc['variable']:
                        md += f"**AI Analysis Verdict:** {analysis['verdict']}\n\n"
                        if analysis.get('suggested_fix'):
                            md += "**Suggested Fix:**\n```python\n"
                            md += analysis['suggested_fix']
                            md += "\n```\n\n"
                        break

        return md
