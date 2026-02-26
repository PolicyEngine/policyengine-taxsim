import React from 'react';

const ErrorMessage = ({ error, retry = null }) => {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="error-card">
        <div className="error-icon">⚠️</div>
        <div className="text-xl text-red-600 mb-2">{error}</div>
        {retry && (
          <button onClick={retry} className="btn-secondary mt-4">
            Try Again
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage;