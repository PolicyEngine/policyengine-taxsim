'use client';

import React from 'react';
import { IconAlertTriangle } from '@tabler/icons-react';
import { STATE_TAX_NOTES } from '../constants';

const StateTaxNote = ({ selectedState, selectedYear }) => {
  const note = STATE_TAX_NOTES[selectedState];

  if (!note) return null;

  // Check if note applies to this year
  const appliesThisYear = note.years === 'all' ||
    (Array.isArray(note.years) && note.years.includes(selectedYear));

  if (!appliesThisYear) return null;

  return (
    <div className="px-6 py-4 bg-warning/10 border-l-4 border-warning rounded-r-lg mt-4 mx-6">
      <div className="flex items-center mb-2">
        <IconAlertTriangle size={20} className="text-warning mr-2" />
        <h3 className="text-sm font-semibold text-secondary-900">
          {note.title}
        </h3>
      </div>
      <div className="text-sm text-gray-600">
        <p>{note.content}</p>
      </div>
    </div>
  );
};

export default StateTaxNote;
