from typing import Dict, Any
import pandas as pd
from .comparator import ComparisonResults
from ..core.utils import get_state_code


class ComparisonStatistics:
    """Generate statistics and reports from comparison results"""
    
    def __init__(self, results: ComparisonResults, input_data: pd.DataFrame = None):
        self.results = results
        self.input_data = input_data
    
    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics dictionary"""
        return {
            'total_records': self.results.total_records,
            'federal_tax': {
                'matches': self.results.federal_match_count,
                'mismatches': len(self.results.federal_mismatches),
                'match_percentage': self.results.federal_match_percentage,
                'tolerance': self.results.config.federal_tolerance
            },
            'state_tax': {
                'matches': self.results.state_match_count,
                'mismatches': len(self.results.state_mismatches),
                'match_percentage': self.results.state_match_percentage,
                'tolerance': self.results.config.state_tolerance
            }
        }
    
    def detailed_report(self) -> str:
        """Generate detailed text report"""
        stats = self.summary()
        
        report = []
        report.append("=" * 60)
        report.append("TAXSIM vs PolicyEngine Comparison Results")
        report.append("=" * 60)
        report.append(f"Total Records Processed: {stats['total_records']:,}")
        report.append("")
        
        # Federal tax results
        report.append("Federal Income Tax Comparison:")
        report.append("-" * 35)
        report.append(f"  Matches:     {stats['federal_tax']['matches']:,} ({stats['federal_tax']['match_percentage']:.2f}%)")
        report.append(f"  Mismatches:  {stats['federal_tax']['mismatches']:,}")
        report.append(f"  Tolerance:   ±${stats['federal_tax']['tolerance']:.0f}")
        report.append("")
        
        # State tax results
        report.append("State Income Tax Comparison:")
        report.append("-" * 32)
        report.append(f"  Matches:     {stats['state_tax']['matches']:,} ({stats['state_tax']['match_percentage']:.2f}%)")
        report.append(f"  Mismatches:  {stats['state_tax']['mismatches']:,}")
        report.append(f"  Tolerance:   ±${stats['state_tax']['tolerance']:.0f}")
        report.append("")
        
        # State-by-state breakdown
        state_stats = self.state_breakdown()
        if state_stats:
            report.append("State-by-State Breakdown:")
            report.append("-" * 27)
            report.append(f"{'State':<6} {'Households':<10} {'Fed Matches':<11} {'State Matches':<12} {'Fed %':<8} {'State %':<8}")
            report.append("-" * 65)
            
            # Sort by state code alphabetically
            for state_code in sorted(state_stats.keys()):
                stats = state_stats[state_code]
                fed_matches = stats['total_households'] - stats['federal_mismatches']
                state_matches = stats['total_households'] - stats['state_mismatches']
                
                report.append(f"{state_code:<6} {stats['total_households']:<10} "
                            f"{fed_matches:<11} {state_matches:<12} "
                            f"{stats['federal_match_rate']:<7.1f}% {stats['state_match_rate']:<7.1f}%")
            report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def state_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Breakdown of households and mismatches by state"""
        breakdown = {}
        
        if self.input_data is None:
            return breakdown
        
        # Get all states in the input data
        if 'state' in self.input_data.columns:
            state_counts = self.input_data['state'].value_counts().to_dict()
            
            for state_fips, total_households in state_counts.items():
                # Count federal mismatches for this state
                federal_mismatches = sum(1 for m in self.results.federal_mismatches 
                                       if hasattr(m, 'state') and m.state == state_fips)
                
                # Count state mismatches for this state
                state_mismatches = sum(1 for m in self.results.state_mismatches 
                                     if hasattr(m, 'state') and m.state == state_fips)
                
                # Convert FIPS to state code
                state_code = get_state_code(state_fips)
                
                breakdown[state_code] = {
                    'state_fips': state_fips,
                    'total_households': total_households,
                    'federal_mismatches': federal_mismatches,
                    'state_mismatches': state_mismatches,
                    'federal_match_rate': ((total_households - federal_mismatches) / total_households * 100) if total_households > 0 else 0,
                    'state_match_rate': ((total_households - state_mismatches) / total_households * 100) if total_households > 0 else 0
                }
        
        return breakdown
    
    def print_summary(self):
        """Print summary to console"""
        stats = self.summary()
        print(f"\nComparison Results (TAXSIM vs PolicyEngine):")
        print(f"Total Records: {stats['total_records']:,}")
        print(f"Federal Tax Matches: {stats['federal_tax']['matches']:,} ({stats['federal_tax']['match_percentage']:.2f}%)")
        print(f"State Tax Matches: {stats['state_tax']['matches']:,} ({stats['state_tax']['match_percentage']:.2f}%)")
