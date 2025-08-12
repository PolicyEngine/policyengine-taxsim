import React, { useState } from 'react';
import { FiArrowUp, FiArrowDown } from 'react-icons/fi';

const StateTable = ({ data, selectedState, onStateSelect }) => {
  const [sortField, setSortField] = useState('federalPct');
  const [sortDirection, setSortDirection] = useState('desc');

  if (!data || !data.summary || !data.summary.stateBreakdown) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">State-by-State Breakdown</h2>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  const { stateBreakdown } = data.summary;

  // Filter and sort data
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

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? <FiArrowUp className="ml-1" /> : <FiArrowDown className="ml-1" />;
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-medium text-gray-900">
          State-by-State Breakdown
          {selectedState && (
            <span className="ml-2 text-sm text-gray-500">
              (Filtered: {selectedState})
            </span>
          )}
        </h2>
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
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedData.map((item, index) => (
              <tr 
                key={index}
                onClick={() => {
                  const newState = item.state === selectedState ? null : item.state;
                  console.log('StateTable click - setting state to:', newState);
                  onStateSelect(newState);
                }}
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {sortedData.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No data available for the selected filters.
        </div>
      )}
    </div>
  );
};

export default StateTable;
