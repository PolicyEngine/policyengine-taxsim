import React from 'react';
import { FiArrowUp, FiArrowDown } from 'react-icons/fi';

const SortableTableHeader = ({ 
  field, 
  label, 
  sortField, 
  sortDirection, 
  onSort 
}) => {
  const SortIcon = () => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? 
      <FiArrowUp className="ml-1" /> : 
      <FiArrowDown className="ml-1" />;
  };

  return (
    <th 
      className="cursor-pointer hover:bg-gray-100"
      onClick={() => onSort(field)}
    >
      <div className="flex items-center">
        {label} <SortIcon />
      </div>
    </th>
  );
};

export default SortableTableHeader;