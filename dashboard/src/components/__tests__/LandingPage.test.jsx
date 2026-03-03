import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LandingPage from '../LandingPage';

describe('LandingPage', () => {
  it('renders hero section', () => {
    render(<LandingPage />);
    expect(screen.getByText('The next chapter of TAXSIM')).toBeInTheDocument();
  });

  it('does not use GitHub install URL (uses PyPI)', () => {
    render(<LandingPage />);
    expect(screen.queryByText(/git\+https:\/\/github\.com/)).not.toBeInTheDocument();
  });

  it('shows all 6 language tabs', () => {
    render(<LandingPage />);
    ['CLI', 'Stata', 'SAS', 'Julia'].forEach(tab => {
      expect(screen.getAllByRole('button', { name: tab }).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders Beyond TAXSIM with CHIP and ACA subsidies', () => {
    const { container } = render(<LandingPage />);
    expect(screen.getAllByText('Beyond TAXSIM').length).toBeGreaterThanOrEqual(1);
    const html = container.innerHTML;
    expect(html).toContain('CHIP');
    expect(html).toContain('ACA marketplace subsidies');
    expect(html).toContain('WIC');
  });

  it('links Enhanced CPS to policyengine.org/us/model', () => {
    render(<LandingPage />);
    const links = screen.getAllByRole('link');
    const ecpsLink = links.find(l => l.textContent.includes('Enhanced CPS'));
    expect(ecpsLink).toBeTruthy();
    expect(ecpsLink.getAttribute('href')).toBe('https://policyengine.org/us/model');
  });

  it('renders NBER and Atlanta Fed validation cards', () => {
    const { container } = render(<LandingPage />);
    expect(container.innerHTML).toContain('NBER partnership');
    expect(container.innerHTML).toContain('Federal Reserve Bank of Atlanta');
  });
});
