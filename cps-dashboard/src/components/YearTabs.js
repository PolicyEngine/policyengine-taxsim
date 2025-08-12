import React from 'react';

const YearTabs = ({ selectedYear, onYearChange }) => {
  const years = [2021, 2022, 2023, 2024];

  return (
    <div className="flex space-x-1">
      {years.map((year) => (
        <button
          key={year}
          onClick={() => onYearChange(year)}
          className={`year-tab ${
            selectedYear === year ? 'active' : 'inactive'
          }`}
        >
          {year}
        </button>
      ))}
    </div>
  );
};

export default YearTabs;
