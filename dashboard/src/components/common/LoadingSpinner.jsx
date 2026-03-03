import React from 'react';

const LoadingSpinner = ({ message = 'Loading...', subMessage = null }) => {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="text-center">
        <div className="loading-spinner-large"></div>
        <div className="text-xl text-gray-600 mb-2 mt-4">{message}</div>
        {subMessage && (
          <div className="text-sm text-gray-500">{subMessage}</div>
        )}
      </div>
    </div>
  );
};

export default LoadingSpinner;