'use client';

import React from 'react';
import { IconAlertTriangle } from '@tabler/icons-react';

const ErrorMessage = ({ error, retry = null }) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-200">
      <div className="bg-white rounded-lg p-10 shadow-lg border-2 border-error/20 max-w-md text-center">
        <div className="flex justify-center mb-4">
          <IconAlertTriangle size={40} className="text-error" />
        </div>
        <div className="text-xl text-error mb-2">{error}</div>
        {retry && (
          <button
            onClick={retry}
            className="inline-flex items-center px-3 py-1.5 rounded-md border border-primary-500 text-primary-500 text-xs font-medium bg-white hover:bg-gray-50 transition mt-4"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage;
