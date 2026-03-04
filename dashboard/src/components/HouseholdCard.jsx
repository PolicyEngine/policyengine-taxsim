'use client';

import React, { useState } from 'react';
import { IconCheck, IconX, IconChevronDown, IconChevronUp, IconDownload } from '@tabler/icons-react';
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
    <div className={`border rounded-lg overflow-hidden transition ${household.hasMismatches ? 'border-error/30' : 'border-success/30'}`}>
      <div
        className={`px-5 py-4 cursor-pointer ${household.hasMismatches ? 'bg-error/5' : 'bg-success/5'}`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white ${household.hasMismatches ? 'bg-error' : 'bg-success'}`}>
              {household.hasMismatches ? <IconX size={16} /> : <IconCheck size={16} />}
            </div>
            <div>
              <div className="font-semibold text-sm text-secondary-900">
                Household ID: {String(household.taxsimid).replace('.0', '')}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                Year: {String(household.year).replace('.0', '')}
                {household.hasMismatches && (
                  <span className="ml-3 text-error font-medium">
                    Total Difference: {formatCurrency(household.totalMismatchAmount)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="text-gray-400">
            {isExpanded ? <IconChevronUp size={20} /> : <IconChevronDown size={20} />}
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="px-5 py-4 border-t border-gray-200">
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setActiveTab('inputs')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${activeTab === 'inputs' ? 'bg-primary-500 text-white' : 'bg-gray-100 text-secondary-900 hover:bg-gray-200'}`}
            >
              Input Values
            </button>
            <button
              onClick={() => setActiveTab('outputs')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${activeTab === 'outputs' ? 'bg-primary-500 text-white' : 'bg-gray-100 text-secondary-900 hover:bg-gray-200'}`}
            >
              Calculated Results
            </button>
          </div>

          <div>
            {activeTab === 'inputs' ? (
              <div>
                {Object.keys(household.inputData).length > 0 && (
                  <div className="flex justify-between items-center mb-4 px-2">
                    <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={hideZeroValues}
                        onChange={(e) => setHideZeroValues(e.target.checked)}
                        className="rounded border-gray-300 scale-[0.8]"
                      />
                      <span>Hide zero values</span>
                    </label>
                    <button
                      onClick={downloadInputData}
                      className="inline-flex items-center px-3 py-1.5 rounded-md border border-primary-500 text-primary-500 text-xs font-medium bg-white hover:bg-gray-50 transition"
                      title="Download input data as CSV"
                    >
                      <IconDownload size={12} className="mr-1" />
                      Download CSV
                    </button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
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
                      <div key={variable.code} className="flex justify-between items-baseline py-1.5 px-3 bg-gray-50 rounded">
                        <div className="min-w-0 mr-2">
                          <span className="text-xs font-mono font-semibold text-secondary-900">{variable.code}</span>
                          <span className="text-xs text-gray-400 ml-1.5">{variable.name}</span>
                        </div>
                        <div className="text-sm font-medium text-secondary-900 whitespace-nowrap">
                          {formatInputValue(variable.code, value)}
                        </div>
                      </div>
                    );
                  })}
                  {Object.keys(household.inputData).length === 0 && (
                    <div className="col-span-full text-center py-6 text-gray-400">
                      <p>Input data not available for this household.</p>
                      <p className="text-sm mt-1">
                        (This may indicate an issue with the data source)
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Variable</th>
                    <th className="bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">TAXSIM</th>
                    <th className="bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">PolicyEngine</th>
                    <th className="bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Difference</th>
                    <th className="bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Status</th>
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
                      <tr key={variable.code} className={diff.hasMismatch ? 'bg-error/5' : ''}>
                        <td className="px-4 py-3 border-b border-gray-100">
                          <div className="font-mono text-xs font-semibold text-secondary-900">{variable.code}</div>
                          <div className="text-xs text-gray-400">{variable.name}</div>
                        </td>
                        <td className="px-4 py-3 border-b border-gray-100 text-left">
                          {formatCurrency(diff.taxsim)}
                        </td>
                        <td className="px-4 py-3 border-b border-gray-100 text-left">
                          {formatCurrency(diff.policyengine)}
                        </td>
                        <td className="px-4 py-3 border-b border-gray-100 text-left">
                          <span className={diff.hasMismatch ? 'text-error font-semibold' : 'text-success'}>
                            {formatDifference(diff.difference)}
                          </span>
                        </td>
                        <td className="px-4 py-3 border-b border-gray-100">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${diff.hasMismatch ? 'bg-error/10 text-error' : 'bg-success/10 text-success'}`}>
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
