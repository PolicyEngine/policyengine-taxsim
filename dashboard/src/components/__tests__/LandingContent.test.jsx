import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LandingContent from '../LandingContent';

describe('LandingContent', () => {
  it('renders hero section', () => {
    render(<LandingContent />);
    expect(screen.getByText('The next chapter of TAXSIM')).toBeInTheDocument();
  });

  it('does not use GitHub install URL (uses PyPI)', () => {
    const { container } = render(<LandingContent />);
    expect(container.innerHTML).not.toContain('git+https');
  });

  it('shows all 6 language tabs', () => {
    render(<LandingContent />);
    ['CLI', 'Python', 'R', 'Stata', 'SAS', 'Julia'].forEach(tab => {
      expect(
        screen.getAllByRole('button', { name: tab }).length
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders Beyond TAXSIM with CHIP and ACA subsidies', () => {
    const { container } = render(<LandingContent />);
    expect(screen.getAllByText('Beyond TAXSIM').length).toBeGreaterThanOrEqual(1);
    const html = container.innerHTML;
    expect(html).toContain('CHIP');
    expect(html).toContain('ACA marketplace subsidies');
    expect(html).toContain('WIC');
  });

  it('links Enhanced CPS to policyengine.org/us/model', () => {
    render(<LandingContent />);
    const links = screen.getAllByRole('link');
    const ecpsLink = links.find(l => l.textContent.includes('Enhanced CPS'));
    expect(ecpsLink).toBeTruthy();
    expect(ecpsLink.getAttribute('href')).toBe('https://policyengine.org/us/model');
  });

  it('renders NBER and Atlanta Fed validation cards', () => {
    const { container } = render(<LandingContent />);
    expect(container.innerHTML).toContain('NBER partnership');
    expect(container.innerHTML).toContain('Federal Reserve Bank of Atlanta');
  });
});
