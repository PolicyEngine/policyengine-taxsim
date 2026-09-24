import JSZip from 'jszip';
import { saveAs } from 'file-saver';
import { assetUrl } from './basePath';
import { AVAILABLE_YEARS, DEFAULT_DATASET } from '../constants';
import { yearDataPath } from './dataLoader';

export const exportAllData = async (dataset = DEFAULT_DATASET) => {
  try {
    const zip = new JSZip();

    for (const year of AVAILABLE_YEARS) {
      const dataPath = assetUrl(`${yearDataPath(year, dataset)}/comparison_results_${year}.csv`);
      
      try {
        const response = await fetch(dataPath);
        if (response.ok) {
          const csvContent = await response.text();
          zip.file(`comparison_results_${year}.csv`, csvContent);
        } else {
          console.warn(`Could not fetch data for year ${year}`);
        }
      } catch (error) {
        console.error(`Error fetching data for year ${year}:`, error);
      }
    }
    
    const content = await zip.generateAsync({ type: 'blob' });
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    saveAs(content, `policyengine-taxsim-${dataset}-sample-${timestamp}.zip`);
    
  } catch (error) {
    console.error('Error exporting data:', error);
    throw new Error('Failed to export data. Please try again.');
  }
};

export const exportYearData = async (year, dataset = DEFAULT_DATASET) => {
  try {
    const dataPath = assetUrl(`${yearDataPath(year, dataset)}/comparison_results_${year}.csv`);
    
    const response = await fetch(dataPath);
    if (!response.ok) {
      throw new Error(`Failed to fetch data for year ${year}`);
    }
    
    const csvContent = await response.text();
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    saveAs(blob, `comparison_results_${dataset}_${year}.csv`);
    
  } catch (error) {
    console.error(`Error exporting data for year ${year}:`, error);
    throw new Error(`Failed to export data for year ${year}. Please try again.`);
  }
};