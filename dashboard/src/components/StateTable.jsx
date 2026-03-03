'use client';

import React, { useState, useCallback } from 'react';
import { IconEye } from '@tabler/icons-react';
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
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6">
          <h2 className="text-lg font-bold text-secondary-900">State-by-State Analysis</h2>
          <div className="animate-pulse mt-4">
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
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
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
              <th className="bg-gray-100 px-6 py-4 text-left text-xs font-semibold text-secondary-900 uppercase tracking-wider border-b-2 border-gray-200">Problem Areas</th>
              <th className="bg-gray-100 px-6 py-4 text-left text-xs font-semibold text-secondary-900 uppercase tracking-wider border-b-2 border-gray-200">Actions</th>
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
  const getColorClass = (pct) => {
    if (pct >= 90) return 'text-success font-semibold';
    if (pct >= 70) return 'text-primary-800 font-semibold';
    return 'text-error font-semibold';
  };
  const getBarColor = (pct) => {
    if (pct >= 90) return '#22c55e';
    if (pct >= 70) return '#38b2ac';
    return '#ef4444';
  };
  const getBarBg = (pct) => {
    if (pct >= 90) return 'rgba(34, 197, 94, 0.08)';
    if (pct >= 70) return 'rgba(56, 178, 172, 0.08)';
    return 'rgba(239, 68, 68, 0.08)';
  };
  const color = getBarColor(value);
  return (
    <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-900 border-b border-gray-100">
      <div>
        <span className={getColorClass(value)}>{value.toFixed(1)}%</span>
        <div className="h-1.5 rounded-full mt-1" style={{ background: getBarBg(value) }}>
          <div className="h-full rounded-full" style={{ width: `${Math.min(value, 100)}%`, background: color }} />
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
      <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-900 border-b border-gray-100 font-medium">{item.state}</td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-900 border-b border-gray-100">{item.households}</td>
      <PctCell value={item.federalPct} />
      <PctCell value={item.statePct} />
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 border-b border-gray-100">
        {getProblemAreas(item)}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-900 border-b border-gray-100" onClick={(e) => e.stopPropagation()}>
        <Button
          onClick={() => onInspect(item.state)}
          variant="secondary"
          size="small"
          icon={<IconEye size={14} />}
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
    <div className="px-6 py-6 border-t border-gray-200">
      <div>
        <div className="flex justify-between flex-wrap gap-4">
          <div className="flex flex-wrap items-center gap-8">
            <h3 className="text-base font-semibold text-secondary-900">
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

      <div className="mt-4">
        {householdData.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No households to display with current filters
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {householdData.slice(0, 50).map((household) => (
              <HouseholdCard
                key={household.taxsimid}
                household={household}
                inputVariables={INPUT_VARIABLES}
                outputVariables={OUTPUT_VARIABLES}
              />
            ))}
            {householdData.length > 50 && (
              <div className="text-center py-4 text-sm text-gray-500">
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
    <div className="flex flex-wrap items-center gap-4">
      <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.showMatches}
          onChange={() => handleFilterChange('showMatches')}
          className="rounded border-gray-300"
        />
        <span>Show Matches</span>
      </label>
      <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.showFederalMismatches}
          onChange={() => handleFilterChange('showFederalMismatches')}
          className="rounded border-gray-300"
        />
        <span>Show Federal Mismatches</span>
      </label>
      <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
        <input
          type="checkbox"
          checked={filters.showStateMismatches}
          onChange={() => handleFilterChange('showStateMismatches')}
          className="rounded border-gray-300"
        />
        <span>Show State Mismatches</span>
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
    <div className="flex items-center gap-2 text-sm ml-auto">
      <span className="text-gray-500">Sort by:</span>
      <select
        value={filters.sortBy}
        onChange={(e) => handleSortChange('sortBy', e.target.value)}
        className="px-3 py-1.5 rounded-md border border-gray-300 bg-white text-sm"
      >
        <option value="taxsimid">Household ID</option>
        <option value="mismatches">Mismatch Amount</option>
      </select>
      <button
        onClick={() => handleSortChange('sortOrder', filters.sortOrder === 'asc' ? 'desc' : 'asc')}
        className="px-2 py-1.5 rounded-md border border-gray-300 bg-white text-sm hover:bg-gray-50 transition"
      >
        {filters.sortOrder === 'asc' ? '\u2191' : '\u2193'}
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
