'use client';

import { useState } from 'react';
import { IconMenu2, IconX, IconChevronDown } from '@tabler/icons-react';
import { assetUrl } from '../utils/basePath';

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

const headerStyle = {
  position: 'sticky',
  top: 0,
  padding: '8px 24px',
  height: '58px',
  backgroundColor: '#2c7a7b',
  borderBottom: '0.5px solid #94A3B8',
  boxShadow: '0px 2px 4px -1px rgba(16, 24, 40, 0.05), 0px 4px 6px -1px rgba(16, 24, 40, 0.1)',
  zIndex: 1000,
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  width: '100%',
  boxSizing: 'border-box',
};

const navLinkStyle = {
  color: '#fff',
  fontWeight: 500,
  fontSize: '18px',
  textDecoration: 'none',
};

export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <header style={headerStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '100%' }}>
        {/* Logo */}
        <a href="https://policyengine.org" style={{ display: 'flex', alignItems: 'center' }}>
          <img
            src={assetUrl('/assets/logos/policyengine/white.svg')}
            alt="PolicyEngine"
            style={{ height: '24px', width: 'auto', marginRight: '12px' }}
          />
        </a>

        {/* Desktop navigation */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '24px' }} className="hidden lg:flex">
          {NAV_ITEMS.map((item) =>
            item.hasDropdown ? (
              <div key={item.label} style={{ position: 'relative' }}>
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  style={{
                    ...navLinkStyle,
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {item.label}
                  <IconChevronDown size={18} color="white" />
                </button>
                {dropdownOpen && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    marginTop: '4px',
                    width: '200px',
                    background: '#fff',
                    borderRadius: '8px',
                    boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
                    border: '1px solid #E2E8F0',
                    padding: '4px 0',
                    zIndex: 1001,
                  }}>
                    {item.items.map((sub) => (
                      <a
                        key={sub.label}
                        href={sub.href}
                        style={{
                          display: 'block',
                          padding: '8px 16px',
                          fontSize: '14px',
                          color: '#101828',
                          textDecoration: 'none',
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f9fafb'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
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
                style={navLinkStyle}
              >
                {item.label}
              </a>
            ),
          )}
        </nav>

        {/* Mobile menu button */}
        <button
          className="lg:hidden"
          style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <IconX size={24} /> : <IconMenu2 size={24} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="lg:hidden" style={{
          backgroundColor: '#285e61',
          borderTop: '1px solid #2c7a7b',
          padding: '16px 24px',
        }}>
          {NAV_ITEMS.map((item) =>
            item.hasDropdown ? (
              <div key={item.label} style={{ padding: '8px 0' }}>
                <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '14px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {item.label}
                </span>
                {item.items.map((sub) => (
                  <a
                    key={sub.label}
                    href={sub.href}
                    style={{ display: 'block', padding: '8px 0 8px 16px', color: '#fff', textDecoration: 'none' }}
                  >
                    {sub.label}
                  </a>
                ))}
              </div>
            ) : (
              <a
                key={item.label}
                href={item.href}
                style={{ display: 'block', padding: '8px 0', color: '#fff', textDecoration: 'none' }}
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
