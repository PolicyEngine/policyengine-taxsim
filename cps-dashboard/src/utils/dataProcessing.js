import { cleanId } from './formatters';

// Process state breakdown data
export const processStateBreakdown = (stateBreakdown, selectedState) => {
  if (!stateBreakdown) return [];
  
  return selectedState 
    ? stateBreakdown.filter(item => item.state === selectedState)
    : stateBreakdown;
};

// Sort state data by field
export const sortStateData = (data, sortField, sortDirection) => {
  return [...data].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    const multiplier = sortDirection === 'asc' ? 1 : -1;
    
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * multiplier;
    }
    return aVal.toString().localeCompare(bVal.toString()) * multiplier;
  });
};

// Calculate aggregate metrics
export const calculateMetrics = (data, selectedState) => {
  if (!data?.summary) return null;
  
  const { summary } = data;
  let displayData = summary;

  // Filter data by state if selected
  if (selectedState && summary.stateBreakdown) {
    const stateData = summary.stateBreakdown.find(
      (state) => state.state === selectedState
    );
    
    if (stateData) {
      displayData = {
        totalRecords: stateData.households,
        federalMatchPct: stateData.federalPct,
        stateMatchPct: stateData.statePct,
      };
    }
  }
  
  return displayData;
};

// Filter households by criteria
export const filterHouseholds = (households, filters) => {
  return households.filter(household => {
    const showMatch = filters.showMatches && !household.hasMismatches;
    const showFederalMismatch = filters.showFederalMismatches && household.hasFederalMismatch;
    const showStateMismatch = filters.showStateMismatches && household.hasStateMismatch;
    
    return showMatch || showFederalMismatch || showStateMismatch;
  });
};

// Sort households
export const sortHouseholds = (households, sortBy, sortOrder) => {
  return [...households].sort((a, b) => {
    let aVal, bVal;
    
    switch (sortBy) {
      case 'taxsimid':
        aVal = parseFloat(cleanId(a.taxsimid));
        bVal = parseFloat(cleanId(b.taxsimid));
        break;
      case 'mismatches':
        aVal = a.totalMismatchAmount;
        bVal = b.totalMismatchAmount;
        break;
      default:
        aVal = a[sortBy];
        bVal = b[sortBy];
    }
    
    if (sortOrder === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });
};

// Create CSV from household input data
export const createHouseholdCSV = (household, inputVariables) => {
  const csvData = [];
  const headers = [];
  const values = [];
  
  // Add basic identifiers first
  ['taxsimid', 'year', 'state'].forEach(field => {
    if (household.inputData[field] !== undefined) {
      headers.push(field);
      values.push(household.inputData[field]);
    }
  });
  
  // Add all other input variables that have values
  inputVariables.forEach(variable => {
    const value = household.inputData[variable.code];
    if (value !== undefined && value !== null && value !== '' && value !== 0) {
      headers.push(variable.code);
      values.push(value);
    }
  });
  
  csvData.push(headers.join(','));
  csvData.push(values.join(','));
  
  return csvData.join('\n');
};

// Download CSV file
export const downloadCSV = (content, filename) => {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};