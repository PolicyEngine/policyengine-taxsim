import { useMemo } from 'react';
import { STATE_TO_FIPS, OUTPUT_VARIABLES, INPUT_FIELDS, MISMATCH_TOLERANCE } from '../constants';
import { cleanId } from '../utils/formatters';

export const useHouseholdData = (data, selectedState, householdFilters) => {
  return useMemo(() => {
    if (!data?.taxsimResults || !data?.policyengineResults || !selectedState) {
      return [];
    }

    const { taxsimResults, policyengineResults, federalMismatches, stateMismatches } = data;
    const fipsCode = STATE_TO_FIPS[selectedState];
    
    // Filter by FIPS code (numeric) or original state value
    // Using == for numeric comparison as state can be string or number
    const filteredTaxsim = taxsimResults.filter(item => 
      // eslint-disable-next-line eqeqeq
      item.state == fipsCode || item.state === selectedState
    );
    
    const filteredPE = policyengineResults.filter(item => 
      // eslint-disable-next-line eqeqeq
      item.state == fipsCode || item.state === selectedState
    );

    // Filter mismatch data for the selected state to get input variables
    const filteredFederalMismatches = federalMismatches?.filter(item => 
      // eslint-disable-next-line eqeqeq
      item.state == fipsCode || item.state === selectedState
    ) || [];
    
    const filteredStateMismatches = stateMismatches?.filter(item => 
      // eslint-disable-next-line eqeqeq
      item.state == fipsCode || item.state === selectedState
    ) || [];

    // Create a combined mismatch lookup for input data
    const mismatchInputData = new Map();
    
    // Add federal mismatch data (contains input variables)
    filteredFederalMismatches.forEach(item => {
      const id = cleanId(item.taxsimid);
      mismatchInputData.set(id, item);
    });
    
    // Add state mismatch data (contains input variables) - merge with existing
    filteredStateMismatches.forEach(item => {
      const id = cleanId(item.taxsimid);
      if (!mismatchInputData.has(id)) {
        mismatchInputData.set(id, item);
      }
    });

    const households = [];

    filteredTaxsim.forEach(taxsimRecord => {
      // Find matching PolicyEngine record
      const peRecord = filteredPE.find(pe => {
        const peId = cleanId(pe.taxsimid);
        const taxsimId = cleanId(taxsimRecord.taxsimid);
        return peId === taxsimId;
      });

      if (peRecord) {
        // Calculate differences for key variables
        const differences = {};
        let hasFederalMismatch = false;
        let hasStateMismatch = false;
        let federalMismatchAmount = 0;
        let stateMismatchAmount = 0;

        OUTPUT_VARIABLES.forEach(variable => {
          const taxsimValue = parseFloat(taxsimRecord[variable.code]) || 0;
          const peValue = parseFloat(peRecord[variable.code]) || 0;
          const diff = taxsimValue - peValue;
          
          differences[variable.code] = {
            taxsim: taxsimValue,
            policyengine: peValue,
            difference: diff,
            hasMismatch: Math.abs(diff) > MISMATCH_TOLERANCE
          };

          // Track federal and state mismatches separately
          if (variable.code === 'fiitax' && Math.abs(diff) > MISMATCH_TOLERANCE) {
            hasFederalMismatch = true;
            federalMismatchAmount = Math.abs(diff);
          }
          if (variable.code === 'siitax' && Math.abs(diff) > MISMATCH_TOLERANCE) {
            hasStateMismatch = true;
            stateMismatchAmount = Math.abs(diff);
          }
        });

        // Determine if household is a match (no mismatches in either federal or state)
        const hasMismatches = hasFederalMismatch || hasStateMismatch;
        const totalMismatchAmount = federalMismatchAmount + stateMismatchAmount;

        // Get input data from consolidated results or fallback to mismatch files
        const householdId = cleanId(taxsimRecord.taxsimid);
        
        // Use consolidated data first (has input data for all households)
        let inputData = {};
        
        // Copy input fields from the taxsim record
        INPUT_FIELDS.forEach(field => {
          if (taxsimRecord[field] !== undefined) {
            inputData[field] = taxsimRecord[field];
          }
        });
        
        // Fallback to mismatch data if consolidated data is not available or incomplete
        const legacyInputData = mismatchInputData.get(householdId) || {};
        Object.keys(legacyInputData).forEach(key => {
          if (inputData[key] === undefined || inputData[key] === null) {
            inputData[key] = legacyInputData[key];
          }
        });

        households.push({
          taxsimid: taxsimRecord.taxsimid,
          year: taxsimRecord.year,
          state: taxsimRecord.state,
          hasMismatches,
          hasFederalMismatch,
          hasStateMismatch,
          totalMismatchAmount,
          federalMismatchAmount,
          stateMismatchAmount,
          differences,
          taxsimRecord,
          peRecord,
          inputData // Include input variables from mismatch data
        });
      }
    });

    // Apply household filters - show household if ANY of the selected criteria match
    let filteredHouseholds = households.filter(household => {
      const showMatch = householdFilters.showMatches && !household.hasMismatches;
      const showFederalMismatch = householdFilters.showFederalMismatches && household.hasFederalMismatch;
      const showStateMismatch = householdFilters.showStateMismatches && household.hasStateMismatch;
      
      return showMatch || showFederalMismatch || showStateMismatch;
    });

    // Sort households
    filteredHouseholds.sort((a, b) => {
      let aVal, bVal;
      
      switch (householdFilters.sortBy) {
        case 'taxsimid':
          aVal = parseFloat(cleanId(a.taxsimid));
          bVal = parseFloat(cleanId(b.taxsimid));
          break;
        case 'mismatches':
          aVal = a.totalMismatchAmount;
          bVal = b.totalMismatchAmount;
          break;
        default:
          aVal = a[householdFilters.sortBy];
          bVal = b[householdFilters.sortBy];
      }
      
      if (householdFilters.sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });

    return filteredHouseholds;
  }, [data, selectedState, householdFilters]);
};