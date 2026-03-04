'use client';

import React from 'react';

const LoadingSpinner = ({ message = 'Loading...', subMessage = null }) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-200">
      <div className="text-center">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-primary-500 rounded-full animate-spin mx-auto"></div>
        <div className="text-xl text-gray-600 mb-2 mt-4">{message}</div>
        {subMessage && (
          <div className="text-sm text-gray-500">{subMessage}</div>
        )}
      </div>
    </div>
  );
};

export default LoadingSpinner;
