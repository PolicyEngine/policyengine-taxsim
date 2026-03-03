'use client';

import { useState } from 'react';
import { IconMenu2, IconX, IconChevronDown } from '@tabler/icons-react';

const NAV_ITEMS = [
  { label: 'Research', href: 'https://policyengine.org/us/research' },
  { label: 'Model', href: 'https://policyengine.org/us/model' },
  {
    label: 'About',
    hasDropdown: true,
    items: [
      { label: 'Team', href: 'https://policyengine.org/us/team' },
      { label: 'Supporters', href: 'https://policyengine.org/us/supporters' },
    ],
  },
  { label: 'Donate', href: 'https://policyengine.org/us/donate' },
];

export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-primary-600 shadow-md">
      <div className="flex items-center justify-between h-[58px] px-6">
        {/* Logo */}
        <a href="https://policyengine.org" className="flex items-center">
          <img
            src="/assets/logos/policyengine/white.svg"
            alt="PolicyEngine"
            className="h-6 w-auto"
          />
        </a>

        {/* Desktop navigation */}
        <nav className="hidden lg:flex items-center gap-6">
          {NAV_ITEMS.map((item) =>
            item.hasDropdown ? (
              <div key={item.label} className="relative">
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-1 bg-transparent border-none cursor-pointer text-white font-medium text-lg"
                >
                  {item.label}
                  <IconChevronDown size={18} color="white" />
                </button>
                {dropdownOpen && (
                  <div className="absolute top-full left-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                    {item.items.map((sub) => (
                      <a
                        key={sub.label}
                        href={sub.href}
                        className="block px-4 py-2 text-sm text-secondary-900 hover:bg-gray-50"
                      >
                        {sub.label}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <a
                key={item.label}
                href={item.href}
                className="text-white font-medium text-lg hover:underline"
              >
                {item.label}
              </a>
            ),
          )}
        </nav>

        {/* Mobile menu button */}
        <button
          className="lg:hidden bg-transparent border-none text-white cursor-pointer"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <IconX size={24} /> : <IconMenu2 size={24} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="lg:hidden bg-primary-700 border-t border-primary-500 px-6 py-4">
          {NAV_ITEMS.map((item) =>
            item.hasDropdown ? (
              <div key={item.label} className="py-2">
                <span className="text-white/70 text-sm font-medium uppercase tracking-wider">
                  {item.label}
                </span>
                {item.items.map((sub) => (
                  <a
                    key={sub.label}
                    href={sub.href}
                    className="block py-2 pl-4 text-white hover:text-primary-200"
                  >
                    {sub.label}
                  </a>
                ))}
              </div>
            ) : (
              <a
                key={item.label}
                href={item.href}
                className="block py-2 text-white hover:text-primary-200"
              >
                {item.label}
              </a>
            ),
          )}
        </div>
      )}
    </header>
  );
}
