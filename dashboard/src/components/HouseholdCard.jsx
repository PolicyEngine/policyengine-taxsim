import React, { useState } from 'react';
import { FiCheck, FiX, FiChevronDown, FiChevronUp, FiDownload } from 'react-icons/fi';
import { formatCurrency, formatDifference, formatInputValue } from '../utils/formatters';

const HouseholdCard = ({ household, inputVariables, outputVariables }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState('inputs');
  const [hideZeroValues, setHideZeroValues] = useState(true);

  const downloadInputData = () => {
    const householdId = String(household.taxsimid).replace('.0', '');
    
    const csvData = [];
    const headers = [];
    const values = [];
    
    ['taxsimid', 'year', 'state'].forEach(field => {
      if (household.inputData[field] !== undefined) {
        headers.push(field);
        values.push(household.inputData[field]);
      }
    });
    
    inputVariables.forEach(variable => {
      const value = household.inputData[variable.code];
      if (value !== undefined && value !== null && value !== '' && value !== 0) {
        headers.push(variable.code);
        values.push(value);
      }
    });
    
    csvData.push(headers.join(','));
    csvData.push(values.join(','));
    
    const csvContent = csvData.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `household_${householdId}_input_data.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={`household-card ${household.hasMismatches ? 'household-card-mismatch' : 'household-card-match'}`}>
      <div 
        className="household-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className={`status-icon ${household.hasMismatches ? 'status-icon-mismatch' : 'status-icon-match'}`}>
              {household.hasMismatches ? <FiX /> : <FiCheck />}
            </div>
            <div>
              <div className="household-id">
                Household ID: {String(household.taxsimid).replace('.0', '')}
              </div>
              <div className="household-meta">
                Year: {String(household.year).replace('.0', '')}
                {household.hasMismatches && (
                  <span className="household-difference">
                    Total Difference: {formatCurrency(household.totalMismatchAmount)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="expand-icon">
            {isExpanded ? <FiChevronUp /> : <FiChevronDown />}
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="household-details">
          <div className="tab-navigation">
            <button
              onClick={() => setActiveTab('inputs')}
              className={`tab-button ${activeTab === 'inputs' ? 'tab-button-active' : ''}`}
            >
              Input Values
            </button>
            <button
              onClick={() => setActiveTab('outputs')}
              className={`tab-button ${activeTab === 'outputs' ? 'tab-button-active' : ''}`}
            >
              Calculated Results
            </button>
          </div>

          <div className="household-table-container">
            {activeTab === 'inputs' ? (
              <div>
                {Object.keys(household.inputData).length > 0 && (
                  <div className="flex justify-between items-center mb-4" style={{ padding: '0 8px' }}>
                    <label className="checkbox-label" style={{ fontSize: '11px', color: '#808080' }}>
                      <input
                        type="checkbox"
                        checked={hideZeroValues}
                        onChange={(e) => setHideZeroValues(e.target.checked)}
                        className="custom-checkbox mr-1"
                        style={{ transform: 'scale(0.8)' }}
                      />
                      <span className="checkbox-text" style={{ fontSize: '11px', color: '#808080' }}>Hide zero values</span>
                    </label>
                    <button
                      onClick={downloadInputData}
                      className="btn-secondary text-xs"
                      title="Download input data as CSV"
                    >
                      <FiDownload className="mr-1" />
                      Download CSV
                    </button>
                  </div>
                )}
                
                <div className="input-variables-grid">
                  {inputVariables.filter(variable => {
                    const value = household.inputData[variable.code];
                    if (value === undefined || value === null || value === '') {
                      return false;
                    }
                    if (hideZeroValues && (value === 0 || value === '0' || value === '0.0' || parseFloat(value) === 0)) {
                      return false;
                    }
                    return true;
                  }).map((variable) => {
                    const value = household.inputData[variable.code];
                    
                    return (
                      <div key={variable.code} className="input-variable-item">
                        <div className="input-variable-label">
                          <span className="input-variable-code">{variable.code}</span>
                          <span className="input-variable-name">{variable.name}</span>
                        </div>
                        <div className="input-variable-value">
                          {formatInputValue(variable.code, value)}
                        </div>
                      </div>
                    );
                  })}
                  {Object.keys(household.inputData).length === 0 && (
                    <div className="input-no-data">
                      <p>Input data not available for this household.</p>
                      <p className="text-sm">
                        (This may indicate an issue with the data source)
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <table className="household-table">
                <thead>
                  <tr>
                    <th>Variable</th>
                    <th>TAXSIM</th>
                    <th>PolicyEngine</th>
                    <th>Difference</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {outputVariables.map((variable) => {
                    // Variables to exclude from display
                    const excludedVariables = [
                      'taxsimid', 'year', 'state', 'v15', 'v16', 'v20', 'v21', 'v23', 'v30', 'v31', 'v33',
                      'v41', 'srebate', 'senergy', 'sptcr', 'samt', 'srate', 'v42', 'v43', 'v45',
                      'v46', 'addmed', 'cdate', 'fica', 'frate', 'ficar'
                    ];

                    if (excludedVariables.includes(variable.code)) return null;

                    const diff = household.differences[variable.code];
                    if (!diff) return null;

                    return (
                      <tr key={variable.code} className={diff.hasMismatch ? 'variable-mismatch' : 'variable-match'}>
                        <td className="variable-info">
                          <div className="variable-code">{variable.code}</div>
                          <div className="variable-name">{variable.name}</div>
                        </td>
                        <td className="value-cell text-left">
                          {formatCurrency(diff.taxsim)}
                        </td>
                        <td className="value-cell text-left">
                          {formatCurrency(diff.policyengine)}
                        </td>
                        <td className="difference-cell text-left">
                          <span className={diff.hasMismatch ? 'difference-mismatch' : 'difference-match'}>
                            {formatDifference(diff.difference)}
                          </span>
                        </td>
                        <td>
                          <span className={`status-badge ${diff.hasMismatch ? 'status-badge-mismatch' : 'status-badge-match'}`}>
                            {diff.hasMismatch ? 'Mismatch' : 'Match'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default HouseholdCard;