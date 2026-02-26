import React, { useState, useCallback } from 'react';
import { FiEye } from 'react-icons/fi';
import GitHubIssues from './GitHubIssues';
import HouseholdCard from './HouseholdCard';
import StateTaxNote from './StateTaxNote';
import SortableTableHeader from './common/SortableTableHeader';
import Button from './common/Button';
import { useHouseholdData } from '../hooks/useHouseholdData';
import { INPUT_VARIABLES, OUTPUT_VARIABLES } from '../constants';
import { getProblemAreas } from '../utils/formatters';
import { sortStateData } from '../utils/dataProcessing';

const StateTable = React.memo(({ data, selectedState, selectedYear, onStateSelect }) => {
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

  const householdData = useHouseholdData(data, selectedState, householdFilters);

  const handleSort = useCallback((field) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  }, [sortField]);

  const handleStateSelect = useCallback((state) => {
    const newState = state === selectedState ? null : state;
    setShowHouseholds(false);
    onStateSelect(newState);
  }, [selectedState, onStateSelect]);

  const toggleHouseholdView = useCallback((state) => {
    if (state !== selectedState) {
      onStateSelect(state);
      setShowHouseholds(true);
    } else {
      setShowHouseholds(prev => !prev);
    }
  }, [selectedState, onStateSelect]);

  if (!data?.summary?.stateBreakdown) {
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
  const filteredData = selectedState 
    ? stateBreakdown.filter(item => item.state === selectedState)
    : stateBreakdown;
  const sortedData = sortStateData(filteredData, sortField, sortDirection);

  const tableHeaders = [
    { field: 'state', label: 'State' },
    { field: 'households', label: 'Households' },
    { field: 'federalPct', label: 'Federal %' },
    { field: 'statePct', label: 'State %' }
  ];

  return (
    <div className="card-container">
      <div className="overflow-x-auto">
        <table className="state-table">
          <thead>
            <tr>
              {tableHeaders.map(header => (
                <SortableTableHeader
                  key={header.field}
                  field={header.field}
                  label={header.label}
                  sortField={sortField}
                  sortDirection={sortDirection}
                  onSort={handleSort}
                />
              ))}
              <th>Problem Areas</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedData.map((item) => (
              <StateRow
                key={item.state}
                item={item}
                isSelected={item.state === selectedState}
                showHouseholds={showHouseholds}
                onSelect={handleStateSelect}
                onInspect={toggleHouseholdView}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* State-specific tax notes */}
      <StateTaxNote selectedState={selectedState} selectedYear={selectedYear} />

      {/* Household Details Section */}
      {selectedState && showHouseholds && (
        <HouseholdSection
          householdData={householdData}
          householdFilters={householdFilters}
          setHouseholdFilters={setHouseholdFilters}
          selectedState={selectedState}
        />
      )}

      {/* GitHub Issues */}
      {selectedState && <GitHubIssues selectedState={selectedState} />}
      
      {sortedData.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No data available for the selected filters.
        </div>
      )}
    </div>
  );
});

// Memoized State Row Component
const PctCell = ({ value }) => {
  const getColor = (pct) => {
    if (pct >= 90) return 'var(--green)';
    if (pct >= 70) return 'var(--teal-accent)';
    return 'var(--dark-red)';
  };
  const getBg = (pct) => {
    if (pct >= 90) return 'rgba(34, 197, 94, 0.08)';
    if (pct >= 70) return 'rgba(56, 178, 172, 0.08)';
    return 'rgba(239, 68, 68, 0.08)';
  };
  const color = getColor(value);
  return (
    <td>
      <div className="dash-pct-cell">
        <span className="dash-pct-value" style={{ color }}>{value.toFixed(1)}%</span>
        <div className="dash-pct-bar-track" style={{ background: getBg(value) }}>
          <div className="dash-pct-bar-fill" style={{ width: `${Math.min(value, 100)}%`, background: color }} />
        </div>
      </div>
    </td>
  );
};

const StateRow = React.memo(({
  item,
  isSelected,
  showHouseholds,
  onSelect,
  onInspect
}) => {
  return (
    <tr
      onClick={() => onSelect(item.state)}
      className={`hover:bg-gray-50 cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
    >
      <td className="font-medium">{item.state}</td>
      <td>{item.households}</td>
      <PctCell value={item.federalPct} />
      <PctCell value={item.statePct} />
      <td className="text-sm text-gray-600">
        {getProblemAreas(item)}
      </td>
      <td onClick={(e) => e.stopPropagation()}>
        <Button
          onClick={() => onInspect(item.state)}
          variant="secondary"
          size="small"
          icon={<FiEye />}
        >
          {isSelected && showHouseholds ? 'Hide' : 'Inspect'}
        </Button>
      </td>
    </tr>
  );
});

// Household Section Component
const HouseholdSection = React.memo(({ 
  householdData, 
  householdFilters, 
  setHouseholdFilters,
  selectedState 
}) => {
  return (
    <div className="household-section">
      <div className="household-controls">
        <div className="flex-between flex-wrap gap-4">
          <div className="flex flex-wrap items-center gap-8">
            <h3 className="section-subtitle">
              Individual Households in {selectedState}
            </h3>
            
            <FilterControls 
              filters={householdFilters}
              setFilters={setHouseholdFilters}
            />
          </div>

          <SortControls
            filters={householdFilters}
            setFilters={setHouseholdFilters}
          />
        </div>
      </div>

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
  );
});

// Filter Controls Component
const FilterControls = React.memo(({ filters, setFilters }) => {
  const handleFilterChange = useCallback((filterName) => {
    setFilters(prev => ({
      ...prev,
      [filterName]: !prev[filterName]
    }));
  }, [setFilters]);

  return (
    <div className="filter-group">
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={filters.showMatches}
          onChange={() => handleFilterChange('showMatches')}
          className="custom-checkbox"
        />
        <span className="checkbox-text">Show Matches</span>
      </label>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={filters.showFederalMismatches}
          onChange={() => handleFilterChange('showFederalMismatches')}
          className="custom-checkbox"
        />
        <span className="checkbox-text">Show Federal Mismatches</span>
      </label>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={filters.showStateMismatches}
          onChange={() => handleFilterChange('showStateMismatches')}
          className="custom-checkbox"
        />
        <span className="checkbox-text">Show State Mismatches</span>
      </label>
    </div>
  );
});

// Sort Controls Component  
const SortControls = React.memo(({ filters, setFilters }) => {
  const handleSortChange = useCallback((field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  }, [setFilters]);

  return (
    <div className="sort-controls ml-auto">
      <span className="sort-label">Sort by:</span>
      <select
        value={filters.sortBy}
        onChange={(e) => handleSortChange('sortBy', e.target.value)}
        className="custom-select"
      >
        <option value="taxsimid">Household ID</option>
        <option value="mismatches">Mismatch Amount</option>
      </select>
      <button
        onClick={() => handleSortChange('sortOrder', filters.sortOrder === 'asc' ? 'desc' : 'asc')}
        className="sort-button"
      >
        {filters.sortOrder === 'asc' ? '↑' : '↓'}
      </button>
    </div>
  );
});

StateTable.displayName = 'StateTable';
StateRow.displayName = 'StateRow';
HouseholdSection.displayName = 'HouseholdSection';
FilterControls.displayName = 'FilterControls';
SortControls.displayName = 'SortControls';

export default StateTable;