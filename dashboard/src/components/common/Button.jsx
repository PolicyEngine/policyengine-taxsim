'use client';

import React from 'react';

const Button = ({
  children,
  onClick,
  variant = 'primary',
  size = 'medium',
  icon = null,
  disabled = false,
  className = '',
  ...props
}) => {
  const variantClasses = {
    primary: 'inline-flex items-center px-4 py-2.5 rounded-lg bg-primary-500 text-white font-semibold text-sm hover:bg-primary-600 transition shadow-sm',
    secondary: 'inline-flex items-center px-3 py-1.5 rounded-md border border-primary-500 text-primary-500 text-xs font-medium bg-white hover:bg-gray-50 transition',
    ghost: 'inline-flex items-center bg-transparent border-none text-primary-500 px-4 py-2 font-medium hover:bg-gray-50 transition rounded-lg'
  };

  const sizeClasses = {
    small: 'px-3 py-1.5 text-xs',
    medium: '',
    large: 'text-base px-6 py-3'
  };

  const classes = [
    variantClasses[variant] || variantClasses.primary,
    size !== 'medium' ? sizeClasses[size] : '',
    disabled ? 'opacity-50 cursor-not-allowed' : '',
    className
  ].filter(Boolean).join(' ');

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={classes}
      {...props}
    >
      {icon && <span className="mr-2">{icon}</span>}
      {children}
    </button>
  );
};

export default Button;
