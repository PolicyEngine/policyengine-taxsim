import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Documentation from '../Documentation';

// Mock the configLoader to avoid fetch issues in tests
vi.mock('../../utils/configLoader', () => ({
  loadConfigurationData: vi.fn().mockResolvedValue({
    variableMappings: [],
    incomeSplittingRules: {},
    systemAssumptions: {},
    implementationDetails: {},
  }),
}));

describe('Documentation', () => {
  it('renders nav and content', () => {
    render(<Documentation />);
    expect(screen.getAllByText('Documentation').length).toBeGreaterThanOrEqual(1);
  });

  it('does not use GitHub install URL (uses PyPI)', () => {
    render(<Documentation />);
    expect(screen.queryByText(/git\+https:\/\/github\.com\/PolicyEngine/)).not.toBeInTheDocument();
  });

  it('shows intro blurb with drop-in replacement and PyPI', () => {
    render(<Documentation />);
    const blurbs = document.querySelectorAll('.doc-intro-blurb');
    const introBlurb = blurbs[0];
    expect(introBlurb.textContent).toContain('drop-in replacement');
    expect(introBlurb.textContent).toContain('pip install policyengine-taxsim');
  });

  it('has all three section tabs', () => {
    render(<Documentation />);
    expect(screen.getAllByText('Installation & Usage').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('All Runners & CLI').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Variable Mappings').length).toBeGreaterThanOrEqual(1);
  });

  it('shows separate installation and usage sections', () => {
    const { container } = render(<Documentation />);
    // Installation heading
    expect(container.innerHTML).toContain('pip install policyengine-taxsim');
    // Usage heading with language tabs
    expect(container.innerHTML).toContain('Same input format, same output variables');
  });

  it('shows all 6 language tabs in usage section', () => {
    render(<Documentation />);
    ['CLI', 'Python', 'R', 'Stata', 'SAS', 'Julia'].forEach(tab => {
      expect(screen.getAllByText(tab).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('R tab shows R package install and auto-setup note', () => {
    render(<Documentation />);
    const rButtons = screen.getAllByText('R');
    fireEvent.click(rButtons[0]);
    const codeBlocks = document.querySelectorAll('code');
    const hasAutoSetup = Array.from(codeBlocks).some(
      el => el.textContent.includes('Python dependencies install automatically')
    );
    expect(hasAutoSetup).toBe(true);
  });

  it('All Runners section shows CLI with stdin/stdout docs', () => {
    render(<Documentation />);
    const runnersButtons = screen.getAllByText('All Runners & CLI');
    fireEvent.click(runnersButtons[0]);
    expect(screen.getAllByText('TaxsimRunner').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Command-Line Interface')).toBeInTheDocument();
    expect(screen.getByText(/reads from stdin and writes to stdout/)).toBeInTheDocument();
  });
});
