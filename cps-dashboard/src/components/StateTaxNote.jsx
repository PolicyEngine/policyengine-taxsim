import React from 'react';
import { STATE_TAX_NOTES } from '../constants';

const StateTaxNote = ({ selectedState, selectedYear }) => {
  const note = STATE_TAX_NOTES[selectedState];
  
  if (!note) return null;
  
  // Check if note applies to this year
  const appliesThisYear = note.years === 'all' || 
    (Array.isArray(note.years) && note.years.includes(selectedYear));
  
  if (!appliesThisYear) return null;

  return (
    <div className="card-container va-rebate-note" style={{ margin: '1.5rem 0' }}>
      <div className="card-header">
        <div className="flex items-center">
          <div className="rebate-note-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <h3 className="rebate-note-title">
            {note.title}
          </h3>
        </div>
      </div>
      <div className="rebate-note-content">
        <p>{note.content}</p>
      </div>
    </div>
  );
};

export default StateTaxNote;