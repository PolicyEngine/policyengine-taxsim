import React, { useState, useMemo } from 'react';
import { FiArrowUp, FiArrowDown, FiChevronDown, FiChevronUp, FiCheck, FiX, FiEye, FiDownload } from 'react-icons/fi';
import GitHubIssues from './GitHubIssues';

const StateTable = ({ data, selectedState, onStateSelect }) => {
  const [sortField, setSortField] = useState('federalPct');
  const [sortDirection, setSortDirection] = useState('desc');
  const [showHouseholds, setShowHouseholds] = useState(false);
  const [householdFilters, setHouseholdFilters] = useState({
    showMatches: true,
    showFederalMismatches: true,
    showStateMismatches: true,
    sortBy: 'taxsimid',
    sortOrder: 'asc'
  });

  // Debug data structure
  console.log('StateTable received data:', {
    hasData: !!data,
    hasSummary: !!data?.summary,
    hasStateBreakdown: !!data?.summary?.stateBreakdown,
    hasTaxsimResults: !!data?.taxsimResults,
    hasPolicyengineResults: !!data?.policyengineResults,
    taxsimResultsLength: data?.taxsimResults?.length,
    policyengineResultsLength: data?.policyengineResults?.length,
    selectedState,
    showHouseholds
  });

  // Define the key input variables for household comparison
  const inputVariables = [
    { code: 'mstat', name: 'Marital Status' },
    { code: 'page', name: 'Primary Taxpayer Age' },
    { code: 'sage', name: 'Spouse Age' },
    { code: 'depx', name: 'Number of Dependents' },
    { code: 'age1', name: 'First Dependent Age' },
    { code: 'age2', name: 'Second Dependent Age' },
    { code: 'pwages', name: 'Primary Wages' },
    { code: 'swages', name: 'Spouse Wages' },
    { code: 'psemp', name: 'Primary Self-Employment' },
    { code: 'ssemp', name: 'Spouse Self-Employment' },
    { code: 'dividends', name: 'Dividend Income' },
    { code: 'intrec', name: 'Interest Income' },
    { code: 'stcg', name: 'Short-Term Capital Gains' },
    { code: 'ltcg', name: 'Long-Term Capital Gains' },
    { code: 'otherprop', name: 'Other Property Income' },
    { code: 'nonprop', name: 'Other Non-Property Income' },
    { code: 'pensions', name: 'Taxable Pensions' },
    { code: 'gssi', name: 'Gross Social Security' },
    { code: 'pui', name: 'Primary Unemployment Income' },
    { code: 'sui', name: 'Spouse Unemployment Income' },
    { code: 'transfers', name: 'Non-Taxable Transfers' },
    { code: 'rentpaid', name: 'Rent Paid' },
    { code: 'proptax', name: 'Property Taxes' },
    { code: 'otheritem', name: 'Other Itemized Deductions' },
    { code: 'childcare', name: 'Child Care Expenses' },
    { code: 'mortgage', name: 'Mortgage Interest' }
  ];

  // Define the key output variables to display in household comparison
  const outputVariables = [
    { code: 'fiitax', name: 'Federal Income Tax' },
    { code: 'siitax', name: 'State Income Tax' },
    { code: 'fica', name: 'FICA Tax' },
    { code: 'tfica', name: 'Total FICA Tax' },
    { code: 'v10', name: 'Federal AGI' },
    { code: 'v11', name: 'UI in AGI' },
    { code: 'v12', name: 'Social Security in AGI' },
    { code: 'v13', name: 'Interest in AGI' },
    { code: 'v14', name: 'Dividends in AGI' },
    { code: 'v17', name: 'Pensions in AGI' },
    { code: 'v18', name: 'Other Income in AGI' },
    { code: 'v19', name: 'Itemized Deductions' },
    { code: 'v22', name: 'Exemption Amount' },
    { code: 'v23', name: 'Taxable Income' },
    { code: 'v24', name: 'Tax Before Credits' },
    { code: 'v25', name: 'Child Tax Credit' },
    { code: 'v26', name: 'EITC' },
    { code: 'v27', name: 'Other Credits' },
    { code: 'v28', name: 'Total Credits' },
    { code: 'v29', name: 'Net Tax' },
    { code: 'v32', name: 'State AGI' },
    { code: 'v34', name: 'State Itemized Deductions' },
    { code: 'v35', name: 'State Standard Deduction' },
    { code: 'v36', name: 'State Exemptions' },
    { code: 'v37', name: 'State Taxable Income' },
    { code: 'v38', name: 'State Tax Before Credits' },
    { code: 'v39', name: 'State Credits' },
    { code: 'v40', name: 'State Net Tax' },
    { code: 'v42', name: 'Total Tax' },
    { code: 'v43', name: 'Marginal Tax Rate' },
    { code: 'v44', name: 'Average Tax Rate' },
    { code: 'v45', name: 'Effective Tax Rate' }
  ];

  const householdData = useMemo(() => {
    if (!data?.taxsimResults || !data?.policyengineResults || !selectedState) {
      console.log('HouseholdData: Missing data or no selected state', {
        hasTaxsimResults: !!data?.taxsimResults,
        hasPolicyengineResults: !!data?.policyengineResults,
        selectedState,
        taxsimLength: data?.taxsimResults?.length,
        peLength: data?.policyengineResults?.length
      });
      return [];
    }

    const { taxsimResults, policyengineResults, federalMismatches, stateMismatches } = data;
    console.log('HouseholdData: Processing data for state', selectedState, {
      taxsimLength: taxsimResults.length,
      peLength: policyengineResults.length,
      federalMismatchesLength: federalMismatches?.length || 0,
      stateMismatchesLength: stateMismatches?.length || 0
    });
    
    // Convert state code to FIPS code for filtering
    // State codes in data are numeric FIPS codes, but UI shows 2-letter codes
    const stateToFips = {
      'AL': 1, 'AK': 2, 'AZ': 3, 'AR': 4, 'CA': 5, 'CO': 6, 'CT': 7, 'DE': 8, 'DC': 9,
      'FL': 10, 'GA': 11, 'HI': 12, 'ID': 13, 'IL': 14, 'IN': 15, 'IA': 16, 'KS': 17,
      'KY': 18, 'LA': 19, 'ME': 20, 'MD': 21, 'MA': 22, 'MI': 23, 'MN': 24, 'MS': 25,
      'MO': 26, 'MT': 27, 'NE': 28, 'NV': 29, 'NH': 30, 'NJ': 31, 'NM': 32, 'NY': 33,
      'NC': 34, 'ND': 35, 'OH': 36, 'OK': 37, 'OR': 38, 'PA': 39, 'RI': 40, 'SC': 41,
      'SD': 42, 'TN': 43, 'TX': 44, 'UT': 45, 'VT': 46, 'VA': 47, 'WA': 48, 'WV': 49,
      'WI': 50, 'WY': 51
    };
    
    const fipsCode = stateToFips[selectedState];
    console.log('State conversion:', { selectedState, fipsCode });
    
    // Filter by FIPS code (numeric) or original state value
    const filteredTaxsim = taxsimResults.filter(item => 
      item.state == fipsCode || item.state === selectedState || item.state == selectedState
    );
    
    const filteredPE = policyengineResults.filter(item => 
      item.state == fipsCode || item.state === selectedState || item.state == selectedState
    );

    // Filter mismatch data for the selected state to get input variables
    const filteredFederalMismatches = federalMismatches?.filter(item => 
      item.state == fipsCode || item.state === selectedState || item.state == selectedState
    ) || [];
    
    const filteredStateMismatches = stateMismatches?.filter(item => 
      item.state == fipsCode || item.state === selectedState || item.state == selectedState
    ) || [];

    // Create a combined mismatch lookup for input data
    const mismatchInputData = new Map();
    
    // Add federal mismatch data (contains input variables)
    filteredFederalMismatches.forEach(item => {
      const id = String(item.taxsimid).replace('.0', '');
      mismatchInputData.set(id, item);
    });
    
    // Add state mismatch data (contains input variables) - merge with existing
    filteredStateMismatches.forEach(item => {
      const id = String(item.taxsimid).replace('.0', '');
      if (!mismatchInputData.has(id)) {
        mismatchInputData.set(id, item);
      }
    });

    console.log('HouseholdData: Filtered data', {
      selectedState,
      selectedStateType: typeof selectedState,
      filteredTaxsimLength: filteredTaxsim.length,
      filteredPELength: filteredPE.length,
      sampleTaxsimStates: taxsimResults.slice(0, 5).map(item => ({state: item.state, type: typeof item.state})),
      samplePEStates: policyengineResults.slice(0, 5).map(item => ({state: item.state, type: typeof item.state})),
      firstTaxsimRecord: filteredTaxsim[0],
      firstPERecord: filteredPE[0]
    });

    const households = [];

    filteredTaxsim.forEach(taxsimRecord => {
      // Find matching PolicyEngine record
      const peRecord = filteredPE.find(pe => {
        const peId = String(pe.taxsimid).replace('.0', '');
        const taxsimId = String(taxsimRecord.taxsimid).replace('.0', '');
        return peId === taxsimId;
      });

      if (peRecord) {
        // Calculate differences for key variables
        const differences = {};
        let hasFederalMismatch = false;
        let hasStateMismatch = false;
        let federalMismatchAmount = 0;
        let stateMismatchAmount = 0;

        outputVariables.forEach(variable => {
          const taxsimValue = parseFloat(taxsimRecord[variable.code]) || 0;
          const peValue = parseFloat(peRecord[variable.code]) || 0;
          const diff = taxsimValue - peValue;
          
          differences[variable.code] = {
            taxsim: taxsimValue,
            policyengine: peValue,
            difference: diff,
            hasMismatch: Math.abs(diff) > 15
          };

          // Track federal and state mismatches separately
          if (variable.code === 'fiitax' && Math.abs(diff) > 15) {
            hasFederalMismatch = true;
            federalMismatchAmount = Math.abs(diff);
          }
          if (variable.code === 'siitax' && Math.abs(diff) > 15) {
            hasStateMismatch = true;
            stateMismatchAmount = Math.abs(diff);
          }
        });

        // Determine if household is a match (no mismatches in either federal or state)
        const hasMismatches = hasFederalMismatch || hasStateMismatch;
        const totalMismatchAmount = federalMismatchAmount + stateMismatchAmount;

        // Get input data from mismatch files if available
        const householdId = String(taxsimRecord.taxsimid).replace('.0', '');
        const inputData = mismatchInputData.get(householdId) || {};

        households.push({
          taxsimid: taxsimRecord.taxsimid,
          year: taxsimRecord.year,
          state: taxsimRecord.state,
          hasMismatches,
          hasFederalMismatch,
          hasStateMismatch,
          totalMismatchAmount,
          federalMismatchAmount,
          stateMismatchAmount,
          differences,
          taxsimRecord,
          peRecord,
          inputData // Include input variables from mismatch data
        });
      }
    });

    // Apply household filters - show household if ANY of the selected criteria match
    let filteredHouseholds = households.filter(household => {
      const showMatch = householdFilters.showMatches && !household.hasMismatches;
      const showFederalMismatch = householdFilters.showFederalMismatches && household.hasFederalMismatch;
      const showStateMismatch = householdFilters.showStateMismatches && household.hasStateMismatch;
      
      return showMatch || showFederalMismatch || showStateMismatch;
    });

    // Sort households
    filteredHouseholds.sort((a, b) => {
      let aVal, bVal;
      
      switch (householdFilters.sortBy) {
        case 'taxsimid':
          aVal = parseFloat(String(a.taxsimid).replace('.0', ''));
          bVal = parseFloat(String(b.taxsimid).replace('.0', ''));
          break;
        case 'mismatches':
          aVal = a.totalMismatchAmount;
          bVal = b.totalMismatchAmount;
          break;
        default:
          aVal = a[householdFilters.sortBy];
          bVal = b[householdFilters.sortBy];
      }
      
      if (householdFilters.sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });

    console.log('HouseholdData: Final result', {
      totalHouseholds: households.length,
      filteredHouseholds: filteredHouseholds.length,
      householdFilters
    });

    return filteredHouseholds;
  }, [data, selectedState, householdFilters, outputVariables]);

  if (!data || !data.summary || !data.summary.stateBreakdown) {
    return (
      <div className="card-container">
        <div className="card-header">
          <h2 className="section-title">State-by-State Analysis</h2>
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  const { stateBreakdown } = data.summary;

  // Filter and sort state data
  let filteredData = selectedState 
    ? stateBreakdown.filter(item => item.state === selectedState)
    : stateBreakdown;

  const sortedData = [...filteredData].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    const multiplier = sortDirection === 'asc' ? 1 : -1;
    
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * multiplier;
    }
    return aVal.toString().localeCompare(bVal.toString()) * multiplier;
  });

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const handleStateSelect = (state) => {
    const newState = state === selectedState ? null : state;
    setShowHouseholds(false); // Reset household view when changing states
    onStateSelect(newState);
  };

  const getPercentageClass = (percentage) => {
    if (percentage >= 80) return 'percentage-good';
    if (percentage >= 60) return 'percentage-warning';
    return 'percentage-poor';
  };

  const getProblemAreas = (item) => {
    const problems = [];
    if (item.federalPct < 70) problems.push('Federal Tax');
    if (item.statePct < 70) problems.push('State Tax');
    return problems.length > 0 ? problems.join(', ') : 'None';
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDifference = (diff) => {
    const sign = diff > 0 ? '+' : '';
    return `${sign}${formatCurrency(diff)}`;
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? <FiArrowUp className="ml-1" /> : <FiArrowDown className="ml-1" />;
  };

  const matchCount = householdData.filter(h => !h.hasMismatches).length;
  const federalMismatchCount = householdData.filter(h => h.hasFederalMismatch).length;
  const stateMismatchCount = householdData.filter(h => h.hasStateMismatch).length;

  return (
    <div className="card-container">
      <div className="card-header">
        <h2 className="section-title">State-by-State Analysis</h2>
        {selectedState && (
          <div className="text-sm font-medium text-gray-600 mt-2">
            Filtered Results: <span className="font-semibold text-gray-900">{selectedState}</span>
            <span className="ml-4">
              <span className="text-green-600">{matchCount} matches</span>
              <span className="mx-2">•</span>
              <span className="text-orange-600">{federalMismatchCount} federal mismatches</span>
              <span className="mx-2">•</span>
              <span className="text-red-600">{stateMismatchCount} state mismatches</span>
            </span>
          </div>
        )}
      </div>
      
      <div className="overflow-x-auto">
        <table className="state-table">
          <thead>
            <tr>
              <th 
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('state')}
              >
                <div className="flex items-center">
                  State <SortIcon field="state" />
                </div>
              </th>
              <th 
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('households')}
              >
                <div className="flex items-center">
                  Households <SortIcon field="households" />
                </div>
              </th>
              <th 
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('federalPct')}
              >
                <div className="flex items-center">
                  Federal % <SortIcon field="federalPct" />
                </div>
              </th>
              <th 
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('statePct')}
              >
                <div className="flex items-center">
                  State % <SortIcon field="statePct" />
                </div>
              </th>
              <th>Problem Areas</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedData.map((item, index) => (
              <tr 
                key={index}
                onClick={() => handleStateSelect(item.state)}
                className={`hover:bg-gray-50 cursor-pointer ${
                  item.state === selectedState ? 'bg-blue-50' : ''
                }`}
              >
                <td className="font-medium">{item.state}</td>
                <td>{item.households}</td>
                <td className={getPercentageClass(item.federalPct)}>
                  {item.federalPct.toFixed(1)}%
                </td>
                <td className={getPercentageClass(item.statePct)}>
                  {item.statePct.toFixed(1)}%
                </td>
                <td className="text-sm text-gray-600">
                  {getProblemAreas(item)}
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => {
                      // If clicking inspect on a different state, switch to that state and show households
                      if (item.state !== selectedState) {
                        onStateSelect(item.state);
                        setShowHouseholds(true);
                      } else {
                        // If same state, toggle household view
                        setShowHouseholds(!showHouseholds);
                      }
                    }}
                    className="btn-secondary text-sm"
                  >
                    <FiEye className="mr-1" />
                    {selectedState === item.state && showHouseholds ? 'Hide' : 'Inspect'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Household Details Section - Only shown when state is selected and user clicks "Inspect" */}
      {selectedState && showHouseholds && (
        <div className="household-section">
          {/* Household Controls */}
          <div className="household-controls">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-8">
                <h3 className="section-subtitle">
                  Individual Households in {selectedState}
                </h3>
                
                {/* Filter Controls */}
                <div className="filter-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={householdFilters.showMatches}
                      onChange={(e) => setHouseholdFilters(prev => ({
                        ...prev,
                        showMatches: e.target.checked
                      }))}
                      className="custom-checkbox"
                    />
                    <span className="checkbox-text">Show Matches</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={householdFilters.showFederalMismatches}
                      onChange={(e) => setHouseholdFilters(prev => ({
                        ...prev,
                        showFederalMismatches: e.target.checked
                      }))}
                      className="custom-checkbox"
                    />
                    <span className="checkbox-text">Show Federal Mismatches</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={householdFilters.showStateMismatches}
                      onChange={(e) => setHouseholdFilters(prev => ({
                        ...prev,
                        showStateMismatches: e.target.checked
                      }))}
                      className="custom-checkbox"
                    />
                    <span className="checkbox-text">Show State Mismatches</span>
                  </label>
                </div>
              </div>

              {/* Sort Controls - moved to the right */}
              <div className="sort-controls ml-auto">
                <span className="sort-label">Sort by:</span>
                <select
                  value={householdFilters.sortBy}
                  onChange={(e) => setHouseholdFilters(prev => ({
                    ...prev,
                    sortBy: e.target.value
                  }))}
                  className="custom-select"
                >
                  <option value="taxsimid">Household ID</option>
                  <option value="mismatches">Mismatch Amount</option>
                </select>
                <button
                  onClick={() => setHouseholdFilters(prev => ({
                    ...prev,
                    sortOrder: prev.sortOrder === 'asc' ? 'desc' : 'asc'
                  }))}
                  className="sort-button"
                >
                  {householdFilters.sortOrder === 'asc' ? '↑' : '↓'}
                </button>
              </div>
            </div>
          </div>

          {/* Household List */}
          <div className="household-list">
            {householdData.length === 0 ? (
              <div className="no-data-message">
                No households to display with current filters
              </div>
            ) : (
              <div className="household-grid">
                {householdData.slice(0, 50).map((household) => (
                  <HouseholdCard 
                    key={household.taxsimid} 
                    household={household} 
                    formatCurrency={formatCurrency} 
                    formatDifference={formatDifference} 
                    inputVariables={inputVariables}
                    outputVariables={outputVariables} 
                  />
                ))}
                {householdData.length > 50 && (
                  <div className="overflow-message">
                    Showing first 50 households. Use filters to narrow results.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* GitHub Issues Section - Always shown when a state is selected */}
      {selectedState && (
        <GitHubIssues selectedState={selectedState} />
      )}
      
      {sortedData.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No data available for the selected filters.
        </div>
      )}
    </div>
  );
};

// Separate component for individual household cards
const HouseholdCard = ({ household, formatCurrency, formatDifference, inputVariables, outputVariables }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState('inputs'); // 'inputs' or 'outputs'

  // Helper function to format input values appropriately
  const formatInputValue = (variableCode, value) => {
    const numericValue = parseFloat(value) || 0;
    
    // Age fields and counts should be integers
    if (['page', 'sage', 'age1', 'age2', 'depx', 'mstat'].includes(variableCode)) {
      if (variableCode === 'mstat') {
        return numericValue === 1 ? 'Single' : numericValue === 2 ? 'Married Filing Jointly' : numericValue.toString();
      }
      return numericValue.toString();
    }
    
    // All other values are currency
    return formatCurrency(numericValue);
  };

  // Function to download input data as CSV
  const downloadInputData = () => {
    const householdId = String(household.taxsimid).replace('.0', '');
    
    // Prepare CSV data with all input variables
    const csvData = [];
    const headers = [];
    const values = [];
    
    // Add basic identifiers first
    ['taxsimid', 'year', 'state'].forEach(field => {
      if (household.inputData[field] !== undefined) {
        headers.push(field);
        values.push(household.inputData[field]);
      }
    });
    
    // Add all other input variables that have values
    inputVariables.forEach(variable => {
      const value = household.inputData[variable.code];
      if (value !== undefined && value !== null && value !== '' && value !== 0) {
        headers.push(variable.code);
        values.push(value);
      }
    });
    
    // Create CSV content
    csvData.push(headers.join(','));
    csvData.push(values.join(','));
    
    const csvContent = csvData.join('\n');
    
    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `household_${householdId}_input_data.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={`household-card ${household.hasMismatches ? 'household-card-mismatch' : 'household-card-match'}`}>
      {/* Household Header */}
      <div 
        className="household-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className={`status-icon ${household.hasMismatches ? 'status-icon-mismatch' : 'status-icon-match'}`}>
              {household.hasMismatches ? <FiX /> : <FiCheck />}
            </div>
            <div>
              <div className="household-id">
                Household ID: {String(household.taxsimid).replace('.0', '')}
              </div>
              <div className="household-meta">
                Year: {household.year} • State: {household.state}
                {household.hasMismatches && (
                  <span className="household-difference">
                    Total Difference: {formatCurrency(household.totalMismatchAmount)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="expand-icon">
            {isExpanded ? <FiChevronUp /> : <FiChevronDown />}
          </div>
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="household-details">
          {/* Tab Navigation */}
          <div className="tab-navigation">
            <button
              onClick={() => setActiveTab('inputs')}
              className={`tab-button ${activeTab === 'inputs' ? 'tab-button-active' : ''}`}
            >
              Input Values
            </button>
            <button
              onClick={() => setActiveTab('outputs')}
              className={`tab-button ${activeTab === 'outputs' ? 'tab-button-active' : ''}`}
            >
              Calculated Results
            </button>
          </div>

          <div className="household-table-container">
            {activeTab === 'inputs' ? (
              <div>
                {/* Download Button for Input Values */}
                {Object.keys(household.inputData).length > 0 && (
                  <div className="flex justify-end mb-4">
                    <button
                      onClick={downloadInputData}
                      className="btn-secondary text-xs"
                      title="Download input data as CSV"
                    >
                      <FiDownload className="mr-1" />
                      Download CSV
                    </button>
                  </div>
                )}
                
                <table className="household-table">
                  <thead>
                    <tr>
                      <th>Variable</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                <tbody>
                  {inputVariables.map((variable) => {
                    const value = household.inputData[variable.code];
                    
                    // Only show if has a meaningful value
                    if (value === undefined || value === null || value === '' || value === 0) {
                      return null;
                    }
                    
                    return (
                      <tr key={variable.code}>
                        <td className="variable-info">
                          <div className="variable-code">{variable.code}</div>
                          <div className="variable-name">{variable.name}</div>
                        </td>
                        <td className="value-cell">
                          {formatInputValue(variable.code, value)}
                        </td>
                      </tr>
                    );
                  })}
                  {Object.keys(household.inputData).length === 0 && (
                    <tr>
                      <td colSpan="2" className="text-center text-gray-500 py-4">
                        Input data not available for this household.
                        <br />
                        <span className="text-sm">
                          (Input data is only available for households that appear in mismatch files)
                        </span>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              </div>
            ) : (
              <table className="household-table">
                <thead>
                  <tr>
                    <th>Variable</th>
                    <th>TAXSIM</th>
                    <th>PolicyEngine</th>
                    <th>Difference</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {outputVariables.map((variable) => {
                    const diff = household.differences[variable.code];
                    if (!diff) return null;
                    
                    return (
                      <tr key={variable.code} className={diff.hasMismatch ? 'variable-mismatch' : 'variable-match'}>
                        <td className="variable-info">
                          <div className="variable-code">{variable.code}</div>
                          <div className="variable-name">{variable.name}</div>
                        </td>
                        <td className="value-cell">
                          {formatCurrency(diff.taxsim)}
                        </td>
                        <td className="value-cell">
                          {formatCurrency(diff.policyengine)}
                        </td>
                        <td className="difference-cell">
                          <span className={diff.hasMismatch ? 'difference-mismatch' : 'difference-match'}>
                            {formatDifference(diff.difference)}
                          </span>
                        </td>
                        <td>
                          <span className={`status-badge ${diff.hasMismatch ? 'status-badge-mismatch' : 'status-badge-match'}`}>
                            {diff.hasMismatch ? 'Mismatch' : 'Match'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default StateTable;