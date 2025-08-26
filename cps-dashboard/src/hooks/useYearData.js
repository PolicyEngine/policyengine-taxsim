import { useState, useEffect } from 'react';
import { loadYearData } from '../utils/dataLoader';
import { AVAILABLE_YEARS } from '../constants';

export const useYearData = (initialYear = 2023) => {
  const [selectedYear, setSelectedYear] = useState(initialYear);
  const [allYearData, setAllYearData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAllData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Loading data for all years
        
        // Load all years in parallel
        const loadPromises = AVAILABLE_YEARS.map(async (year) => {
          try {
            const yearData = await loadYearData(year);
            return { year, data: yearData };
          } catch (err) {
            console.warn(`Failed to load data for year ${year}:`, err);
            return { year, data: null, error: err.message };
          }
        });
        
        const results = await Promise.all(loadPromises);
        
        // Build the data object
        const dataByYear = {};
        let hasAnyData = false;
        
        results.forEach(({ year, data, error }) => {
          if (data) {
            dataByYear[year] = data;
            hasAnyData = true;
          } else if (error) {
            console.error(`Year ${year} failed to load:`, error);
          }
        });
        
        if (!hasAnyData) {
          throw new Error('Failed to load data for any year');
        }
        
        setAllYearData(dataByYear);
        // All year data loaded successfully
        
      } catch (err) {
        console.error('Error loading data:', err);
        setError('Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  }, []); // Only run once on mount

  const currentYearData = allYearData[selectedYear] || null;
  const availableYears = Object.keys(allYearData).map(Number);

  return {
    selectedYear,
    setSelectedYear,
    currentYearData,
    allYearData,
    availableYears,
    loading,
    error
  };
};