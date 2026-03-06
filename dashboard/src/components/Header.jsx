'use client';

import { useState, useRef, useEffect } from 'react';
import { IconMenu2, IconChevronDown, IconWorld, IconX } from '@tabler/icons-react';
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

const COUNTRIES = [
  { id: 'us', label: 'United States' },
  { id: 'uk', label: 'United Kingdom' },
];

const linkStyle = {
  color: '#fff',
  fontWeight: 500,
  fontSize: '18px',
  textDecoration: 'none',
  fontFamily: "'Inter', sans-serif",
};

export default function Header() {
  const [aboutOpen, setAboutOpen] = useState(false);
  const [countryOpen, setCountryOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const aboutRef = useRef(null);
  const countryRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (aboutRef.current && !aboutRef.current.contains(e.target)) setAboutOpen(false);
      if (countryRef.current && !countryRef.current.contains(e.target)) setCountryOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        padding: '8px 24px',
        height: '58px',
        backgroundColor: '#2C7A7B',
        borderBottom: '0.5px solid #94A3B8',
        boxShadow: '0px 2px 4px -1px rgba(16,24,40,0.05), 0px 4px 6px -1px rgba(16,24,40,0.1)',
        zIndex: 1000,
        fontFamily: "'Inter', sans-serif",
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '100%' }}>
        {/* Left: Logo + Desktop Nav */}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <a href="https://policyengine.org/us" style={{ display: 'flex', alignItems: 'center', marginRight: '12px' }}>
            <img
              src={assetUrl('/assets/logos/policyengine/white.svg')}
              alt="PolicyEngine"
              style={{ height: '24px', width: 'auto' }}
            />
          </a>

          <nav style={{ display: 'flex', alignItems: 'center', gap: '24px' }} className="hidden lg:flex">
            {NAV_ITEMS.map((item) =>
              item.hasDropdown ? (
                <div key={item.label} ref={aboutRef} style={{ position: 'relative' }}>
                  <button
                    onClick={() => setAboutOpen(!aboutOpen)}
                    style={{
                      ...linkStyle,
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
                  {aboutOpen && (
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
                            fontFamily: "'Inter', sans-serif",
                          }}
                        >
                          {sub.label}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <a key={item.label} href={item.href} style={linkStyle}>
                  {item.label}
                </a>
              ),
            )}
          </nav>
        </div>

        {/* Right: Country selector (desktop) */}
        <div className="hidden lg:flex" style={{ display: 'flex', alignItems: 'center' }}>
          <div ref={countryRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setCountryOpen(!countryOpen)}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1 }}
              aria-label="Country selector"
            >
              <IconWorld size={18} color="white" />
            </button>
            {countryOpen && (
              <div style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: '4px',
                width: '200px',
                background: '#fff',
                borderRadius: '8px',
                boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
                border: '1px solid #E2E8F0',
                padding: '4px 0',
                zIndex: 1001,
              }}>
                {COUNTRIES.map((c) => (
                  <a
                    key={c.id}
                    href={`https://policyengine.org/${c.id}`}
                    style={{
                      display: 'block',
                      padding: '8px 16px',
                      fontSize: '14px',
                      color: '#101828',
                      textDecoration: 'none',
                      fontFamily: "'Inter', sans-serif",
                      fontWeight: c.id === 'us' ? 700 : 400,
                    }}
                  >
                    {c.label}
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Mobile: Country selector + hamburger */}
        <div className="flex lg:hidden" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setCountryOpen(!countryOpen)}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1 }}
              aria-label="Country selector"
            >
              <IconWorld size={18} color="white" />
            </button>
          </div>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px' }}
            aria-label="Toggle navigation"
          >
            <IconMenu2 size={24} color="white" />
          </button>
        </div>
      </div>

      {/* Mobile slide-in menu */}
      {mobileOpen && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)', zIndex: 1001 }}
            onClick={() => setMobileOpen(false)}
          />
          <div style={{
            position: 'fixed',
            top: 0,
            right: 0,
            width: '300px',
            height: '100vh',
            backgroundColor: '#2C7A7B',
            zIndex: 1002,
            padding: '16px 24px',
            fontFamily: "'Inter', sans-serif",
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <span style={{ color: '#fff', fontWeight: 700, fontSize: '16px' }}>Menu</span>
              <button
                onClick={() => setMobileOpen(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                aria-label="Close menu"
              >
                <IconX size={24} color="white" />
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {NAV_ITEMS.map((item) =>
                item.hasDropdown ? (
                  <div key={item.label}>
                    <span style={{ color: '#fff', fontWeight: 500, fontSize: '14px', display: 'block', marginBottom: '4px' }}>
                      {item.label}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '12px' }}>
                      {item.items.map((sub) => (
                        <a key={sub.label} href={sub.href} style={{ color: '#fff', textDecoration: 'none', fontSize: '14px' }}>
                          {sub.label}
                        </a>
                      ))}
                    </div>
                  </div>
                ) : (
                  <a key={item.label} href={item.href} style={{ color: '#fff', textDecoration: 'none', fontWeight: 500, fontSize: '14px', display: 'block' }}>
                    {item.label}
                  </a>
                ),
              )}
            </div>
          </div>
        </>
      )}
    </header>
  );
}
