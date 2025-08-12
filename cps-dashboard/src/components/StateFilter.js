import React from 'react';

const StateFilter = ({ selectedState, onStateChange }) => {
  const states = [
    { code: null, name: 'All States' },
    { code: 'CA', name: 'California' },
    { code: 'TX', name: 'Texas' },
    { code: 'NY', name: 'New York' },
    { code: 'FL', name: 'Florida' },
    { code: 'IL', name: 'Illinois' },
    { code: 'PA', name: 'Pennsylvania' },
    { code: 'OH', name: 'Ohio' },
    { code: 'GA', name: 'Georgia' },
    { code: 'NC', name: 'North Carolina' },
    { code: 'MI', name: 'Michigan' },
    { code: 'HI', name: 'Hawaii' },
  ];

  return (
    <div className="flex items-center space-x-2">
      <label htmlFor="state-filter" className="text-sm font-medium text-gray-700">
        State:
      </label>
      <select
        id="state-filter"
        value={selectedState || ''}
        onChange={(e) => onStateChange(e.target.value || null)}
        className="select"
      >
        {states.map((state) => (
          <option key={state.code || 'all'} value={state.code || ''}>
            {state.name}
          </option>
        ))}
      </select>
    </div>
  );
};

export default StateFilter;
