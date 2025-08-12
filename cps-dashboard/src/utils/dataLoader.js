import Papa from 'papaparse';

// Parse the comparison report text file
const parseComparisonReport = (text) => {
  const lines = text.split('\n');
  
  // Extract total records
  const totalRecordsLine = lines.find(line => line.includes('Total Records Processed:'));
  const totalRecords = totalRecordsLine ? parseInt(totalRecordsLine.split(':')[1].trim().replace(/,/g, '')) : 0;
  
  // Extract federal match data - look for the first "Matches:" line
  const federalMatchLine = lines.find(line => line.includes('Matches:') && line.includes('(') && line.includes('%'));
  const federalMatches = federalMatchLine ? parseInt(federalMatchLine.split('(')[1].split('%')[0]) : 0;
  
  // Extract state match data - look for the second "Matches:" line by filtering out the first one
  const allMatchLines = lines.filter(line => line.includes('Matches:') && line.includes('(') && line.includes('%'));
  const stateMatchLine = allMatchLines.length > 1 ? allMatchLines[1] : null;
  const stateMatches = stateMatchLine ? parseInt(stateMatchLine.split('(')[1].split('%')[0]) : 0;
  
  // Parse state breakdown
  const stateBreakdown = [];
  const stateDataStartIndex = lines.findIndex(line => line.includes('State  Households'));
  
  if (stateDataStartIndex > -1) {
    for (let i = stateDataStartIndex + 2; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.includes('=====')) break;
      
      const parts = line.split(/\s+/);
      if (parts.length >= 6) {
        stateBreakdown.push({
          state: parts[0],
          households: parseInt(parts[1]) || 0,
          federalMatches: parseInt(parts[2]) || 0,
          stateMatches: parseInt(parts[3]) || 0,
          federalPct: parseFloat(parts[4]) || 0,
          statePct: parseFloat(parts[6]) || 0,
        });
      }
    }
  }
  
  return {
    totalRecords,
    federalMatchPct: federalMatches,
    stateMatchPct: stateMatches,
    stateBreakdown
  };
};

// Global cache for loaded data
const dataCache = new Map();

// Load CSV data with caching
const loadCSVData = async (url) => {
  // Check cache first
  if (dataCache.has(url)) {
    console.log(`Loading ${url} from cache`);
    return dataCache.get(url);
  }

  try {
    console.log(`Loading ${url} from server`);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const text = await response.text();
    
    return new Promise((resolve, reject) => {
      Papa.parse(text, {
        header: true,
        complete: (results) => {
          if (results.errors.length > 0) {
            console.warn('CSV parsing warnings:', results.errors);
          }
          // Cache the results
          dataCache.set(url, results.data);
          resolve(results.data);
        },
        error: (error) => reject(error)
      });
    });
  } catch (error) {
    console.error(`Error loading CSV from ${url}:`, error);
    throw error;
  }
};

// Load text data with caching
const loadTextData = async (url) => {
  // Check cache first
  if (dataCache.has(url)) {
    console.log(`Loading ${url} from cache`);
    return dataCache.get(url);
  }

  try {
    console.log(`Loading ${url} from server`);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const text = await response.text();
    // Cache the results
    dataCache.set(url, text);
    return text;
  } catch (error) {
    console.error(`Error loading text from ${url}:`, error);
    throw error;
  }
};

// Main function to load all data for a given year
export const loadYearData = async (year) => {
  const baseUrl = `/data/${year}`;
  
  try {
    // Load comparison report
    const reportText = await loadTextData(`${baseUrl}/comparison_report_${year}.txt`);
    const summary = parseComparisonReport(reportText);
    
    // Load mismatch data (for backward compatibility)
    let federalMismatches = [];
    let stateMismatches = [];
    
    try {
      federalMismatches = await loadCSVData(`${baseUrl}/federal_mismatches_${year}.csv`);
      stateMismatches = await loadCSVData(`${baseUrl}/state_mismatches_${year}.csv`);
    } catch (error) {
      console.log('Mismatch files not found, will use results files for detailed analysis');
    }
    
    // Load full results for detailed variable analysis
    let taxsimResults = [];
    let policyengineResults = [];
    
    try {
      taxsimResults = await loadCSVData(`${baseUrl}/taxsim_results_${year}.csv`);
      policyengineResults = await loadCSVData(`${baseUrl}/policyengine_results_${year}.csv`);
    } catch (error) {
      console.log('Results files not found, using mismatch data only');
    }
    
    return {
      year,
      summary,
      federalMismatches,
      stateMismatches,
      taxsimResults,
      policyengineResults
    };
  } catch (error) {
    console.error(`Error loading data for year ${year}:`, error);
    throw error;
  }
};

// State code to name mapping
export const STATE_MAPPING = {
  1: 'AL', 2: 'AK', 3: 'AZ', 4: 'AR', 5: 'CA', 6: 'CA', 7: 'CO', 8: 'CT', 9: 'DE', 10: 'DC',
  11: 'FL', 12: 'FL', 13: 'GA', 14: 'HI', 15: 'ID', 16: 'IL', 17: 'IN', 18: 'IA', 19: 'KS', 20: 'KY',
  21: 'LA', 22: 'ME', 23: 'MD', 24: 'MA', 25: 'MI', 26: 'MN', 27: 'MS', 28: 'MO', 29: 'MT', 30: 'NE',
  31: 'NV', 32: 'NH', 33: 'NJ', 34: 'NM', 35: 'NY', 36: 'NY', 37: 'NC', 38: 'ND', 39: 'OH', 40: 'OK',
  41: 'OR', 42: 'PA', 43: 'RI', 44: 'SC', 45: 'SD', 46: 'TN', 47: 'TX', 48: 'TX', 49: 'UT', 50: 'VT',
  51: 'VA', 52: 'WA', 53: 'WV', 54: 'WI', 55: 'WY'
};

export const getStateName = (stateCode) => {
  if (typeof stateCode === 'string' && stateCode.length === 2) {
    return stateCode;
  }
  return STATE_MAPPING[stateCode] || stateCode;
};

// Utility function to clear cache if needed
export const clearDataCache = () => {
  dataCache.clear();
  console.log('Data cache cleared');
};

// Utility function to get cache info
export const getCacheInfo = () => {
  return {
    size: dataCache.size,
    keys: Array.from(dataCache.keys())
  };
};
