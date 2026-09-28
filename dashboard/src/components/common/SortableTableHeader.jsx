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
      className="bg-gray-50 px-6 py-3 text-left font-mono text-[11px] font-semibold text-gray-500 uppercase tracking-[0.12em] border-b border-gray-200 cursor-pointer hover:text-gray-900 transition select-none"
      onClick={() => onSort(field)}
    >
      <div className="flex items-center">
        {label} <SortIcon />
      </div>
    </th>
  );
};

export default SortableTableHeader;
