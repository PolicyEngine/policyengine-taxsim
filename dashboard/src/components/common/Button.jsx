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
  const baseClasses = 'inline-flex items-center font-semibold transition-all duration-200';
  
  const variantClasses = {
    primary: 'btn',
    secondary: 'btn-secondary',
    ghost: 'btn-ghost'
  };
  
  const sizeClasses = {
    small: 'text-xs px-2 py-1',
    medium: 'text-sm px-4 py-2',
    large: 'text-base px-6 py-3'
  };
  
  const classes = `
    ${baseClasses}
    ${variantClasses[variant] || variantClasses.primary}
    ${sizeClasses[size] || sizeClasses.medium}
    ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
    ${className}
  `.trim();
  
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