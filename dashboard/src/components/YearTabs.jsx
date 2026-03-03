'use client';

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
            className={`px-5 py-3 rounded-lg font-semibold border-2 border-transparent cursor-pointer transition mr-2 ${
              isSelected
                ? 'bg-primary-500 text-white'
                : isAvailable
                  ? 'bg-gray-100 text-secondary-900 border-gray-200 hover:bg-gray-200'
                  : 'opacity-50 cursor-not-allowed bg-gray-200 text-gray-400'
            }`}
            title={!isAvailable ? `Data for ${year} is not available` : ''}
          >
            {year}
          </button>
        );
      })}
    </div>
  );
};

export default YearTabs;
