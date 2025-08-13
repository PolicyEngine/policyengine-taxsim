import React, { useState, useMemo, useCallback } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';

const VariableAnalysis = ({ data, selectedState }) => {
  const [activeTab, setActiveTab] = useState('all');
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Define the variables we want to analyze
  const targetVariables = [
    { code: 'fiitax', name: 'Federal Income Tax', category: 'tax' },
    { code: 'siitax', name: 'State Income Tax', category: 'tax' },
    { code: 'fica', name: 'FICA Taxes', category: 'tax' },
    { code: 'tfica', name: 'Total FICA', category: 'tax' },
    { code: 'v10', name: 'Adjusted Gross Income', category: 'income' },
    { code: 'v11', name: 'UI Benefits', category: 'income' },
    { code: 'v12', name: 'Social Security Benefits', category: 'income' },
    { code: 'v13', name: 'Standard Deduction', category: 'deduction' },
    { code: 'v14', name: 'Personal Exemptions', category: 'deduction' },
    { code: 'v17', name: 'Itemized Deductions', category: 'deduction' },
    { code: 'v18', name: 'Taxable Income', category: 'income' },
    { code: 'v19', name: 'Tax Before Credits', category: 'tax' },
    { code: 'v22', name: 'Child Tax Credit', category: 'credit' },
    { code: 'v23', name: 'Additional Child Tax Credit', category: 'credit' },
    { code: 'v24', name: 'Child Care Credit', category: 'credit' },
    { code: 'v25', name: 'Earned Income Credit', category: 'credit' },
    { code: 'v26', name: 'Total Income', category: 'income' },
    { code: 'v27', name: 'Federal Tax Withheld', category: 'tax' },
    { code: 'v28', name: 'Tax After Credits', category: 'tax' },
    { code: 'v29', name: 'FICA Withheld', category: 'tax' },
    { code: 'v32', name: 'Adjusted Gross Income 2', category: 'income' },
    { code: 'v34', name: 'Standard/Itemized Deduction Used', category: 'deduction' },
    { code: 'v35', name: 'Personal Exemption Amount', category: 'deduction' },
    { code: 'v36', name: 'Taxable Income After Exemptions', category: 'income' },
    { code: 'v37', name: 'Tax Calculation Method', category: 'tax' },
    { code: 'v38', name: 'Tax Rate Schedule', category: 'tax' },
    { code: 'v39', name: 'Alternative Minimum Tax', category: 'tax' },
    { code: 'v40', name: 'Tax Credits Applied', category: 'credit' },
    { code: 'v42', name: 'State Income Before Credits', category: 'tax' },
    { code: 'v43', name: 'State Credits', category: 'credit' },
    { code: 'v44', name: 'State Tax After Credits', category: 'tax' },
    { code: 'v45', name: 'Additional State Taxes', category: 'credit' },
  ];

  const calculateDistribution = (differences) => {
    const absValues = differences.map(d => Math.abs(d));
    const ranges = [
      { min: 0, max: 50, label: '$0-50' },
      { min: 50, max: 100, label: '$50-100' },
      { min: 100, max: 250, label: '$100-250' },
      { min: 250, max: 500, label: '$250-500' },
      { min: 500, max: Infinity, label: '$500+' }
    ];

    return ranges.map(range => ({
      range: range.label,
      count: absValues.filter(val => val >= range.min && val < range.max).length
    }));
  };

  const compareResults = useCallback((taxsimResults, policyengineResults, selectedState) => {
    if (!taxsimResults || !policyengineResults || taxsimResults.length === 0 || policyengineResults.length === 0) {
      return [];
    }

    // Filter by state if selected
    const filteredTaxsim = selectedState 
      ? taxsimResults.filter(item => item.state === selectedState || item.state === selectedState)
      : taxsimResults;
    
    const filteredPE = selectedState
      ? policyengineResults.filter(item => item.state === selectedState || item.state === selectedState)
      : policyengineResults;



    const analysis = [];
    
    targetVariables.forEach((variable) => {
      const differences = [];
      
      // Match records by taxsimid and compare
      filteredTaxsim.forEach(taxsimRecord => {
        const peRecord = filteredPE.find(pe => {
          // Handle both string and numeric taxsimid formats
          const peId = String(pe.taxsimid).replace('.0', '');
          const taxsimId = String(taxsimRecord.taxsimid).replace('.0', '');
          return peId === taxsimId;
        });
        
        if (peRecord) {
          const taxsimValue = parseFloat(taxsimRecord[variable.code]) || 0;
          const peValue = parseFloat(peRecord[variable.code]) || 0;
          const diff = taxsimValue - peValue;
          

          
          if (Math.abs(diff) > 15) { // Only include differences outside $15 tolerance
            differences.push(diff);
          }
        }
      });



      if (differences.length > 0) {
        const avgDiff = differences.reduce((sum, diff) => sum + Math.abs(diff), 0) / differences.length;
        const maxDiff = Math.max(...differences.map(diff => Math.abs(diff)));
        
        analysis.push({
          variable: variable.code,
          name: variable.name,
          category: variable.category,
          count: differences.length,
          totalRecords: filteredTaxsim.length,
          mismatchRate: (differences.length / filteredTaxsim.length) * 100,
          avgDiff: avgDiff,
          maxDiff: maxDiff,
          distribution: calculateDistribution(differences)
        });
      }
    });

    // Sort by mismatch count (most problematic first)
    return analysis.sort((a, b) => b.count - a.count);
  }, [targetVariables]);

  const analysisData = useMemo(() => {
    if (!data) return { all: [], tax: [], income: [], deduction: [], credit: [] };

    // Use full results for comprehensive analysis if available
    if (data.taxsimResults && data.policyengineResults) {
      const allAnalysis = compareResults(data.taxsimResults, data.policyengineResults, selectedState);
      
      return {
        all: allAnalysis,
        tax: allAnalysis.filter(item => item.category === 'tax'),
        income: allAnalysis.filter(item => item.category === 'income'),
        deduction: allAnalysis.filter(item => item.category === 'deduction'),
        credit: allAnalysis.filter(item => item.category === 'credit')
      };
    }

    // Fallback to simple mismatch analysis for backward compatibility
    return { all: [], tax: [], income: [], deduction: [], credit: [] };
  }, [data, selectedState, compareResults]);

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const currentData = analysisData[activeTab] || [];

  if (!data) {
    return (
      <div className="card-container">
        <div className="card-header">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card-container">
      {/* Collapsible Header */}
      <div 
        className="card-header cursor-pointer" 
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center justify-between">
          <div>
            <h2 className="section-title mb-0 pb-0">Variable Mismatch Analysis</h2>
            {selectedState && (
              <div className="text-sm font-medium text-gray-600 mt-2">
                Filtered Results: <span className="font-semibold text-gray-900">{selectedState}</span>
              </div>
            )}
          </div>
          <div className="text-2xl text-gray-500">
            {isCollapsed ? <FiChevronDown /> : <FiChevronUp />}
          </div>
        </div>
      </div>

      {/* Collapsible Content */}
      {!isCollapsed && (
        <div>
          {/* Standard Tabs */}
          <div className="border-b border-gray-200">
            <nav className="flex space-x-8 px-6">
              <button
                onClick={() => setActiveTab('all')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'all'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                All Variables
              </button>
              <button
                onClick={() => setActiveTab('tax')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'tax'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Tax Variables
              </button>
              <button
                onClick={() => setActiveTab('income')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'income'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Income Variables
              </button>
              <button
                onClick={() => setActiveTab('deduction')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'deduction'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Deductions
              </button>
              <button
                onClick={() => setActiveTab('credit')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'credit'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Credits
              </button>
            </nav>
          </div>

          <div className="p-6">
            {currentData.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No mismatches found for {activeTab} variables
                {selectedState && ` in ${selectedState}`}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Variable
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Mismatches
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Mismatch Rate
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Avg Difference
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Max Difference
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Impact
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {currentData.map((item, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {item.variable}
                            </div>
                            <div className="text-sm text-gray-500">
                              {item.name}
                            </div>
                            <div className="text-xs text-gray-400 capitalize">
                              {item.category}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {item.count}
                          <div className="text-xs text-gray-500">
                            of {item.totalRecords}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          <span className={`font-semibold ${
                            item.mismatchRate > 50 
                              ? 'text-red-600'
                              : item.mismatchRate > 20
                              ? 'text-yellow-600'
                              : 'text-green-600'
                          }`}>
                            {item.mismatchRate.toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatCurrency(item.avgDiff)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatCurrency(item.maxDiff)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            item.mismatchRate > 50 || item.avgDiff > 1000
                              ? 'bg-red-100 text-red-800'
                              : item.mismatchRate > 20 || item.avgDiff > 100
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-green-100 text-green-800'
                          }`}>
                            {item.mismatchRate > 50 || item.avgDiff > 1000 ? 'High' : 
                             item.mismatchRate > 20 || item.avgDiff > 100 ? 'Medium' : 'Low'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VariableAnalysis;
