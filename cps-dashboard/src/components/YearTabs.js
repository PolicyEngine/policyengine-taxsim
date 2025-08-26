import React from 'react';
import { AVAILABLE_YEARS } from '../constants';

const YearTabs = ({ selectedYear, onYearChange, availableYears = [] }) => {
  const years = AVAILABLE_YEARS;

  return (
    <div className="flex space-x-1">
      {years.map((year) => {
        const isAvailable = availableYears.includes(year);
        const isSelected = selectedYear === year;
        
        return (
          <button
            key={year}
            onClick={() => isAvailable && onYearChange(year)}
            disabled={!isAvailable}
            className={`year-tab ${
              isSelected ? 'active' : 'inactive'
            } ${!isAvailable ? 'disabled' : ''}`}
            title={!isAvailable ? `Data for ${year} is not available` : ''}
          >
            {year}
            {!isAvailable && <span className="ml-1 text-xs opacity-60">⏳</span>}
          </button>
        );
      })}
    </div>
  );
};

export default YearTabs;
