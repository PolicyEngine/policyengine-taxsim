import React from 'react';

const StateFilter = ({ selectedState, onStateChange, availableStates }) => {
  // Create states list dynamically from available data + common states
  const defaultStates = [
    { code: null, name: 'All States' },
    { code: 'AL', name: 'Alabama' },
    { code: 'AK', name: 'Alaska' },
    { code: 'AR', name: 'Arkansas' },
    { code: 'AZ', name: 'Arizona' },
    { code: 'CA', name: 'California' },
    { code: 'CO', name: 'Colorado' },
    { code: 'CT', name: 'Connecticut' },
    { code: 'DC', name: 'District of Columbia' },
    { code: 'DE', name: 'Delaware' },
    { code: 'FL', name: 'Florida' },
    { code: 'GA', name: 'Georgia' },
    { code: 'HI', name: 'Hawaii' },
    { code: 'IA', name: 'Iowa' },
    { code: 'ID', name: 'Idaho' },
    { code: 'IL', name: 'Illinois' },
    { code: 'IN', name: 'Indiana' },
    { code: 'KS', name: 'Kansas' },
    { code: 'KY', name: 'Kentucky' },
    { code: 'LA', name: 'Louisiana' },
    { code: 'MA', name: 'Massachusetts' },
    { code: 'MD', name: 'Maryland' },
    { code: 'ME', name: 'Maine' },
    { code: 'MI', name: 'Michigan' },
    { code: 'MN', name: 'Minnesota' },
    { code: 'MO', name: 'Missouri' },
    { code: 'MS', name: 'Mississippi' },
    { code: 'MT', name: 'Montana' },
    { code: 'NC', name: 'North Carolina' },
    { code: 'ND', name: 'North Dakota' },
    { code: 'NE', name: 'Nebraska' },
    { code: 'NH', name: 'New Hampshire' },
    { code: 'NJ', name: 'New Jersey' },
    { code: 'NM', name: 'New Mexico' },
    { code: 'NV', name: 'Nevada' },
    { code: 'NY', name: 'New York' },
    { code: 'OH', name: 'Ohio' },
    { code: 'OK', name: 'Oklahoma' },
    { code: 'OR', name: 'Oregon' },
    { code: 'PA', name: 'Pennsylvania' },
    { code: 'RI', name: 'Rhode Island' },
    { code: 'SC', name: 'South Carolina' },
    { code: 'SD', name: 'South Dakota' },
    { code: 'TN', name: 'Tennessee' },
    { code: 'TX', name: 'Texas' },
    { code: 'UT', name: 'Utah' },
    { code: 'VA', name: 'Virginia' },
    { code: 'VT', name: 'Vermont' },
    { code: 'WA', name: 'Washington' },
    { code: 'WI', name: 'Wisconsin' },
    { code: 'WV', name: 'West Virginia' },
    { code: 'WY', name: 'Wyoming' },
    { code: 'N/A', name: 'Other/Unknown' },
  ];

  // If we have available states from data, make sure they're all included
  const states = defaultStates;

  return (
    <div className="flex items-center space-x-2">
      <label htmlFor="state-filter" className="text-sm font-medium text-gray-700">
        State:
      </label>
      <select
        id="state-filter"
        value={selectedState || ''}
        onChange={(e) => {
          console.log('StateFilter onChange:', e.target.value);
          onStateChange(e.target.value || null);
        }}
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
