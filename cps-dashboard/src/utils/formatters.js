// Currency formatting
export const formatCurrency = (value) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

// Format difference with sign
export const formatDifference = (diff) => {
  const sign = diff > 0 ? '+' : '';
  return `${sign}${formatCurrency(diff)}`;
};

// Format date to readable string
export const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

// Get CSS class for percentage value
export const getPercentageClass = (percentage) => {
  if (percentage >= 80) return 'percentage-good';
  if (percentage >= 60) return 'percentage-warning';
  return 'percentage-poor';
};

// Format input values appropriately based on variable type
export const formatInputValue = (variableCode, value, formatCurrencyFn = formatCurrency) => {
  const numericValue = parseFloat(value) || 0;
  
  // Age fields and counts should be integers
  const integerFields = ['page', 'sage', 'age1', 'age2', 'age3', 'age4', 'age5', 
                         'age6', 'age7', 'age8', 'age9', 'age10', 'age11', 'depx', 'mstat'];
  
  if (integerFields.includes(variableCode)) {
    if (variableCode === 'mstat') {
      return numericValue === 1 ? 'Single' : numericValue === 2 ? 'Married Filing Jointly' : numericValue.toString();
    }
    return numericValue.toString();
  }
  
  // All other values are currency
  return formatCurrencyFn(numericValue);
};

// Clean ID string (remove .0 suffix)
export const cleanId = (id) => {
  return String(id).replace('.0', '');
};

// Get problem areas for a state based on match percentages
export const getProblemAreas = (item) => {
  const problems = [];
  if (item.federalPct < 70) problems.push('Federal Tax');
  if (item.statePct < 70) problems.push('State Tax');
  return problems.length > 0 ? problems.join(', ') : 'None';
};