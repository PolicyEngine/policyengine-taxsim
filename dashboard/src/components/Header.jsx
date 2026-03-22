'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { IconChevronDown, IconMenu2, IconWorld, IconX } from '@tabler/icons-react';
import { assetUrl } from '../utils/basePath';

// Design system tokens (from @policyengine/design-system)
const colors = {
  primary: {
    500: '#319795',
    600: '#2C7A7B',
    700: '#285E61',
    800: '#234E52',
  },
  text: { inverse: '#FFFFFF' },
  shadow: {
    light: 'rgba(16, 24, 40, 0.05)',
    medium: 'rgba(16, 24, 40, 0.1)',
  },
};

const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  '2xl': '24px',
  layout: { header: '58px' },
};

const typography = {
  fontFamily: {
    primary: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  fontWeight: { normal: 400, medium: 500, semibold: 600, bold: 700 },
  fontSize: { sm: '14px', lg: '18px' },
};

const COUNTRY_ID = 'us';

const COUNTRIES = [
  { id: 'us', label: 'United States' },
  { id: 'uk', label: 'United Kingdom' },
];

const navItemStyle = {
  color: colors.text.inverse,
  fontWeight: typography.fontWeight.medium,
  fontSize: '15px',
  fontFamily: typography.fontFamily.primary,
  textDecoration: 'none',
  padding: '6px 14px',
  borderRadius: '6px',
  transition: 'background-color 0.15s ease',
  letterSpacing: '0.01em',
};

const hoverHandlers = {
  onMouseEnter: (e) => {
    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.12)';
  },
  onMouseLeave: (e) => {
    e.currentTarget.style.backgroundColor = 'transparent';
  },
};

const NAV_ITEMS = [
  {
    label: 'Research',
    href: `https://policyengine.org/${COUNTRY_ID}/research`,
    hasDropdown: false,
  },
  {
    label: 'Model',
    href: `https://policyengine.org/${COUNTRY_ID}/model`,
    hasDropdown: false,
  },
  {
    label: 'API',
    href: `https://policyengine.org/${COUNTRY_ID}/api`,
    hasDropdown: false,
  },
  {
    label: 'About',
    hasDropdown: true,
    dropdownItems: [
      { label: 'Team', href: `https://policyengine.org/${COUNTRY_ID}/team` },
      { label: 'Supporters', href: `https://policyengine.org/${COUNTRY_ID}/supporters` },
      { label: 'Citations', href: `https://policyengine.org/${COUNTRY_ID}/citations` },
    ],
  },
  {
    label: 'Donate',
    href: `https://policyengine.org/${COUNTRY_ID}/donate`,
    hasDropdown: false,
  },
];

// --- Apple-style dropdown panel ---

function DropdownPanel({ items, open, onClose }) {
  const contentRef = useRef(null);
  const [contentHeight, setContentHeight] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (open && contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
      requestAnimationFrame(() => setVisible(true));
    } else {
      setVisible(false);
      const timer = setTimeout(() => setContentHeight(0), 250);
      return () => clearTimeout(timer);
    }
  }, [open]);

  if (!open && contentHeight === 0) return null;

  return (
    <>
      {/* Click-away layer */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 999, cursor: 'default' }}
      />
      <div
        style={{
          position: 'absolute',
          top: '100%',
          left: '50%',
          transform: visible
            ? 'translateX(-50%) translateY(0)'
            : 'translateX(-50%) translateY(-8px)',
          marginTop: '10px',
          minWidth: '220px',
          overflow: 'hidden',
          maxHeight: visible ? `${contentHeight}px` : '0px',
          opacity: visible ? 1 : 0,
          transition:
            'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease, transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          borderRadius: '14px',
          background:
            'linear-gradient(135deg, rgba(255,255,255,0.97), rgba(240,249,255,0.95))',
          backdropFilter: 'blur(24px) saturate(200%)',
          WebkitBackdropFilter: 'blur(24px) saturate(200%)',
          boxShadow:
            '0 20px 60px rgba(0, 0, 0, 0.15), 0 4px 16px rgba(0, 0, 0, 0.06), inset 0 0 0 1px rgba(255, 255, 255, 0.6)',
          zIndex: 1001,
        }}
      >
        <div ref={contentRef} style={{ padding: '8px' }}>
          {items.map((item, i) => (
            <a
              key={item.label}
              href={item.href}
              onClick={onClose}
              style={{
                display: 'flex',
                alignItems: 'center',
                width: '100%',
                textAlign: 'left',
                padding: '11px 16px',
                borderRadius: '10px',
                textDecoration: 'none',
                fontSize: '14px',
                fontFamily: typography.fontFamily.primary,
                fontWeight: typography.fontWeight.semibold,
                color: colors.primary[800],
                transition:
                  'background-color 0.12s ease, color 0.12s ease, opacity 0.3s ease',
                transitionDelay: visible ? `${i * 50}ms` : '0ms',
                opacity: visible ? 1 : 0,
                lineHeight: '1.3',
                letterSpacing: '-0.01em',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = colors.primary[500];
                e.currentTarget.style.color = colors.text.inverse;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = colors.primary[800];
              }}
            >
              {item.label}
            </a>
          ))}
        </div>
      </div>
    </>
  );
}

// --- NavItem ---

function NavItem({ setup }) {
  const { label, href, hasDropdown, dropdownItems } = setup;
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!dropdownOpen) return;
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    function handleKey(e) {
      if (e.key === 'Escape') setDropdownOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [dropdownOpen]);

  if (hasDropdown && dropdownItems) {
    return (
      <div ref={containerRef} style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setDropdownOpen((prev) => !prev)}
          style={{
            ...navItemStyle,
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
          {...hoverHandlers}
        >
          <span>{label}</span>
          <IconChevronDown
            size={15}
            color={colors.text.inverse}
            style={{
              opacity: 0.7,
              transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: dropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            }}
          />
        </button>
        <DropdownPanel
          items={dropdownItems}
          open={dropdownOpen}
          onClose={() => setDropdownOpen(false)}
        />
      </div>
    );
  }

  if (href) {
    return (
      <a href={href} style={navItemStyle} {...hoverHandlers}>
        {label}
      </a>
    );
  }

  return null;
}

// --- Country selector ---

function CountrySelector() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);
  const contentRef = useRef(null);
  const [contentHeight, setContentHeight] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (open && contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
      requestAnimationFrame(() => setVisible(true));
    } else {
      setVisible(false);
      const timer = setTimeout(() => setContentHeight(0), 250);
      return () => clearTimeout(timer);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    function handleKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Country selector"
        style={{
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          padding: '6px',
          borderRadius: '6px',
          transition: 'background-color 0.15s ease',
          lineHeight: 1,
          display: 'flex',
          alignItems: 'center',
        }}
        {...hoverHandlers}
      >
        <IconWorld size={18} color={colors.text.inverse} />
      </button>

      {(open || contentHeight > 0) && (
        <>
          <div
            onClick={() => setOpen(false)}
            style={{ position: 'fixed', inset: 0, zIndex: 999, cursor: 'default' }}
          />
          <div
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              transform: visible ? 'translateY(0)' : 'translateY(-8px)',
              marginTop: '10px',
              minWidth: '220px',
              overflow: 'hidden',
              maxHeight: visible ? `${contentHeight}px` : '0px',
              opacity: visible ? 1 : 0,
              transition:
                'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease, transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              borderRadius: '14px',
              background:
                'linear-gradient(135deg, rgba(255,255,255,0.97), rgba(240,249,255,0.95))',
              backdropFilter: 'blur(24px) saturate(200%)',
              WebkitBackdropFilter: 'blur(24px) saturate(200%)',
              boxShadow:
                '0 20px 60px rgba(0, 0, 0, 0.15), 0 4px 16px rgba(0, 0, 0, 0.06), inset 0 0 0 1px rgba(255, 255, 255, 0.6)',
              zIndex: 1001,
            }}
          >
            <div ref={contentRef} style={{ padding: '8px' }}>
              {COUNTRIES.map((country, i) => (
                <a
                  key={country.id}
                  href={`https://policyengine.org/${country.id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    width: '100%',
                    textAlign: 'left',
                    padding: '11px 16px',
                    borderRadius: '10px',
                    textDecoration: 'none',
                    fontSize: '14px',
                    fontFamily: typography.fontFamily.primary,
                    fontWeight:
                      COUNTRY_ID === country.id
                        ? typography.fontWeight.bold
                        : typography.fontWeight.semibold,
                    color: colors.primary[800],
                    transition:
                      'background-color 0.12s ease, color 0.12s ease, opacity 0.3s ease',
                    transitionDelay: visible ? `${i * 50}ms` : '0ms',
                    opacity: visible ? 1 : 0,
                    lineHeight: '1.3',
                    letterSpacing: '-0.01em',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = colors.primary[500];
                    e.currentTarget.style.color = colors.text.inverse;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.color = colors.primary[800];
                  }}
                >
                  {country.label}
                </a>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// --- Mobile menu ---

function MobileMenu({ open, onClose }) {
  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.4)',
        }}
      />
      {/* Panel */}
      <div
        style={{
          position: 'relative',
          width: '300px',
          height: '100%',
          backgroundColor: colors.primary[600],
          padding: spacing.lg,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.lg,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span
            style={{
              color: colors.text.inverse,
              fontWeight: typography.fontWeight.semibold,
              fontSize: typography.fontSize.lg,
              fontFamily: typography.fontFamily.primary,
            }}
          >
            Menu
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <IconX size={20} color={colors.text.inverse} />
          </button>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.lg,
          }}
        >
          {NAV_ITEMS.map((item) =>
            item.hasDropdown && item.dropdownItems ? (
              <div key={item.label}>
                <span
                  style={{
                    color: colors.text.inverse,
                    fontWeight: typography.fontWeight.medium,
                    fontSize: typography.fontSize.sm,
                    marginBottom: spacing.xs,
                    display: 'block',
                    fontFamily: typography.fontFamily.primary,
                  }}
                >
                  {item.label}
                </span>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: spacing.xs,
                    paddingLeft: spacing.md,
                  }}
                >
                  {item.dropdownItems.map((dropdownItem) => (
                    <a
                      key={dropdownItem.label}
                      href={dropdownItem.href}
                      onClick={onClose}
                      style={{
                        color: colors.text.inverse,
                        textDecoration: 'none',
                        fontWeight: typography.fontWeight.normal,
                        fontSize: typography.fontSize.sm,
                        fontFamily: typography.fontFamily.primary,
                      }}
                    >
                      {dropdownItem.label}
                    </a>
                  ))}
                </div>
              </div>
            ) : (
              <a
                key={item.label}
                href={item.href}
                onClick={onClose}
                style={{
                  color: colors.text.inverse,
                  textDecoration: 'none',
                  fontWeight: typography.fontWeight.medium,
                  fontSize: typography.fontSize.sm,
                  fontFamily: typography.fontFamily.primary,
                  display: 'block',
                }}
              >
                {item.label}
              </a>
            ),
          )}
        </div>
      </div>
    </div>
  );
}

// --- Main Header ---

export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        padding: `${spacing.sm} ${spacing['2xl']}`,
        height: spacing.layout.header,
        background: `linear-gradient(to right, ${colors.primary[800]}, ${colors.primary[600]})`,
        borderBottom: `0.5px solid ${colors.primary[700]}`,
        boxShadow: `0px 2px 4px -1px ${colors.shadow.light}, 0px 4px 6px -1px ${colors.shadow.medium}`,
        zIndex: 1000,
        fontFamily: typography.fontFamily.primary,
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          height: '100%',
        }}
      >
        {/* Left: logo + desktop nav */}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <a
            href={`https://policyengine.org/${COUNTRY_ID}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              marginRight: spacing.md,
            }}
          >
            <img
              src={assetUrl('/assets/logos/policyengine/white.svg')}
              alt="PolicyEngine"
              style={{ height: '24px', width: 'auto', marginRight: 12 }}
            />
          </a>

          {/* Desktop nav */}
          <div
            className="hidden lg:flex"
            style={{ alignItems: 'center', gap: '24px' }}
          >
            {NAV_ITEMS.map((item) => (
              <NavItem key={item.label} setup={item} />
            ))}
          </div>
        </div>

        {/* Right: country selector (desktop) */}
        <div className="hidden lg:flex" style={{ alignItems: 'center' }}>
          <CountrySelector />
        </div>

        {/* Right: mobile controls */}
        <div
          className="flex lg:hidden"
          style={{ alignItems: 'center', gap: spacing.md }}
        >
          <CountrySelector />
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Toggle navigation"
            style={{
              padding: '4px',
              borderRadius: '4px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            <IconMenu2 size={24} color={colors.text.inverse} />
          </button>
        </div>
      </div>

      <MobileMenu open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </header>
  );
}
