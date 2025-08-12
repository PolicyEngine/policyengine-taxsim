import React, { useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const VariableAnalysis = ({ data, selectedState }) => {
  const [activeTab, setActiveTab] = useState('federal');

  const calculateDistribution = (differences) => {
    const absValues = differences.map(d => Math.abs(d));
    const ranges = [
      { min: 0, max: 50, label: '$0-50' },
      { min: 50, max: 100, label: '$50-100' },
      { min: 100, max: 250, label: '$100-250' },
      { min: 250, max: 500, label: '$250-500' },
      { min: 500, max: Infinity, label: '$500+' }
    ];

    return ranges.map(range => ({
      range: range.label,
      count: absValues.filter(val => val >= range.min && val < range.max).length
    }));
  };

  const analyzeMismatches = (mismatches, differenceField) => {
    if (!mismatches || mismatches.length === 0) return [];

    // For now, we'll analyze the main tax difference
    // In a real implementation, you'd analyze multiple output variables
    const differences = mismatches
      .map(item => parseFloat(item[differenceField]) || 0)
      .filter(diff => Math.abs(diff) > 0);

    if (differences.length === 0) return [];

    const avgDiff = differences.reduce((sum, diff) => sum + Math.abs(diff), 0) / differences.length;
    const maxDiff = Math.max(...differences.map(diff => Math.abs(diff)));
    const minDiff = Math.min(...differences.map(diff => Math.abs(diff)));

    return [{
      variable: differenceField === 'federal_difference' ? 'fiitax' : 'siitax',
      name: differenceField === 'federal_difference' ? 'Federal Income Tax' : 'State Income Tax',
      count: differences.length,
      avgDiff: avgDiff,
      maxDiff: maxDiff,
      minDiff: minDiff,
      distribution: calculateDistribution(differences)
    }];
  };

  const analysisData = useMemo(() => {
    if (!data) return { federal: [], state: [] };

    const federalMismatches = data.federalMismatches || [];
    const stateMismatches = data.stateMismatches || [];

    // Filter by state if selected
    const filteredFederal = selectedState 
      ? federalMismatches.filter(item => item.state === selectedState || item.state === selectedState)
      : federalMismatches;
    
    const filteredState = selectedState
      ? stateMismatches.filter(item => item.state === selectedState || item.state === selectedState)
      : stateMismatches;

    // Analyze federal mismatches
    const federalAnalysis = analyzeMismatches(filteredFederal, 'federal_difference');
    
    // Analyze state mismatches  
    const stateAnalysis = analyzeMismatches(filteredState, 'state_difference');

    return {
      federal: federalAnalysis,
      state: stateAnalysis
    };
  }, [data, selectedState]);

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const currentData = analysisData[activeTab] || [];

  if (!data) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Variable Mismatch Analysis</h2>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-medium text-gray-900 mb-4">
          Output Variable Mismatch Analysis
          {selectedState && (
            <span className="ml-2 text-sm text-gray-500">
              (Filtered: {selectedState})
            </span>
          )}
        </h2>
        
        {/* Tabs */}
        <div className="flex space-x-1">
          <button
            onClick={() => setActiveTab('federal')}
            className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
              activeTab === 'federal'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Federal Variables
          </button>
          <button
            onClick={() => setActiveTab('state')}
            className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
              activeTab === 'state'
                ? 'bg-green-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            State Variables
          </button>
        </div>
      </div>

      <div className="p-6">
        {currentData.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No mismatches found for {activeTab} variables
            {selectedState && ` in ${selectedState}`}.
          </div>
        ) : (
          <div className="space-y-6">
            {/* Variable Summary Table */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Variable
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Mismatches
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Avg Difference
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Max Difference
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Impact
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {currentData.map((item, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {item.variable}
                          </div>
                          <div className="text-sm text-gray-500">
                            {item.name}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {item.count}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(item.avgDiff)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(item.maxDiff)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          item.avgDiff > 500 
                            ? 'bg-red-100 text-red-800'
                            : item.avgDiff > 100
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {item.avgDiff > 500 ? 'High' : item.avgDiff > 100 ? 'Medium' : 'Low'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Distribution Chart */}
            {currentData[0] && currentData[0].distribution && (
              <div>
                <h3 className="text-md font-medium text-gray-900 mb-4">
                  Difference Distribution
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={currentData[0].distribution}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="range" />
                      <YAxis />
                      <Tooltip />
                      <Bar 
                        dataKey="count" 
                        fill={activeTab === 'federal' ? '#3B82F6' : '#10B981'} 
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default VariableAnalysis;
