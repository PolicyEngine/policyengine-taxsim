import React, { useState, useMemo } from 'react';
import { FiArrowUp, FiArrowDown, FiEye } from 'react-icons/fi';
import GitHubIssues from './GitHubIssues';
import HouseholdCard from './HouseholdCard';
import StateTaxNote from './StateTaxNote';
import { STATE_TO_FIPS, INPUT_VARIABLES, OUTPUT_VARIABLES, INPUT_FIELDS, MISMATCH_TOLERANCE } from '../constants';
import { formatCurrency, formatDifference, getPercentageClass, getProblemAreas, cleanId } from '../utils/formatters';

const StateTable = ({ data, selectedState, selectedYear, onStateSelect }) => {
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




  const householdData = useMemo(() => {
    if (!data?.taxsimResults || !data?.policyengineResults || !selectedState) {
      return [];
    }

    const { taxsimResults, policyengineResults, federalMismatches, stateMismatches } = data;
    
    const fipsCode = STATE_TO_FIPS[selectedState];
    
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


    const households = [];

    filteredTaxsim.forEach(taxsimRecord => {
      // Find matching PolicyEngine record
      const peRecord = filteredPE.find(pe => {
        const peId = cleanId(pe.taxsimid);
        const taxsimId = cleanId(taxsimRecord.taxsimid);
        return peId === taxsimId;
      });

      if (peRecord) {
        // Calculate differences for key variables
        const differences = {};
        let hasFederalMismatch = false;
        let hasStateMismatch = false;
        let federalMismatchAmount = 0;
        let stateMismatchAmount = 0;

        OUTPUT_VARIABLES.forEach(variable => {
          const taxsimValue = parseFloat(taxsimRecord[variable.code]) || 0;
          const peValue = parseFloat(peRecord[variable.code]) || 0;
          const diff = taxsimValue - peValue;
          
          differences[variable.code] = {
            taxsim: taxsimValue,
            policyengine: peValue,
            difference: diff,
            hasMismatch: Math.abs(diff) > MISMATCH_TOLERANCE
          };

          // Track federal and state mismatches separately
          if (variable.code === 'fiitax' && Math.abs(diff) > MISMATCH_TOLERANCE) {
            hasFederalMismatch = true;
            federalMismatchAmount = Math.abs(diff);
          }
          if (variable.code === 'siitax' && Math.abs(diff) > MISMATCH_TOLERANCE) {
            hasStateMismatch = true;
            stateMismatchAmount = Math.abs(diff);
          }
        });

        // Determine if household is a match (no mismatches in either federal or state)
        const hasMismatches = hasFederalMismatch || hasStateMismatch;
        const totalMismatchAmount = federalMismatchAmount + stateMismatchAmount;

        // Get input data from consolidated results or fallback to mismatch files
        const householdId = cleanId(taxsimRecord.taxsimid);
        
        // Use consolidated data first (has input data for all households)
        let inputData = {};
        
        // Copy input fields from the taxsim record
        INPUT_FIELDS.forEach(field => {
          if (taxsimRecord[field] !== undefined) {
            inputData[field] = taxsimRecord[field];
          }
        });
        
        // Fallback to mismatch data if consolidated data is not available or incomplete
        const legacyInputData = mismatchInputData.get(householdId) || {};
        Object.keys(legacyInputData).forEach(key => {
          if (inputData[key] === undefined || inputData[key] === null) {
            inputData[key] = legacyInputData[key];
          }
        });

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
          aVal = parseFloat(cleanId(a.taxsimid));
          bVal = parseFloat(cleanId(b.taxsimid));
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


    return filteredHouseholds;
  }, [data, selectedState, householdFilters]);

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


  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? <FiArrowUp className="ml-1" /> : <FiArrowDown className="ml-1" />;
  };



  return (
    <div className="card-container">
      
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

      {/* State-specific rebate notes - shown when state is selected */}
      <StateTaxNote selectedState={selectedState} selectedYear={selectedYear} />

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
                    inputVariables={INPUT_VARIABLES}
                    outputVariables={OUTPUT_VARIABLES} 
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

export default StateTable;