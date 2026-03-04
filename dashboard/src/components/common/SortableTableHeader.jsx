'use client';

import React from 'react';
import { IconArrowUp, IconArrowDown } from '@tabler/icons-react';

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
      <IconArrowUp size={14} className="ml-1" /> :
      <IconArrowDown size={14} className="ml-1" />;
  };

  return (
    <th
      className="bg-gray-100 px-6 py-4 text-left text-xs font-semibold text-secondary-900 uppercase tracking-wider border-b-2 border-gray-200 cursor-pointer hover:bg-gray-200 transition"
      onClick={() => onSort(field)}
    >
      <div className="flex items-center">
        {label} <SortIcon />
      </div>
    </th>
  );
};

export default SortableTableHeader;
