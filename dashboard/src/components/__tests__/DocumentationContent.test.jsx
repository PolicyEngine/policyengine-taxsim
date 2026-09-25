import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import DocumentationContent from '../DocumentationContent';

// Mock the configLoader to avoid fetch issues in tests
vi.mock('../../utils/configLoader', () => ({
  loadConfigurationData: vi.fn().mockResolvedValue({
    variableMappings: [],
    incomeSplittingRules: {},
    systemAssumptions: {},
    implementationDetails: {},
  }),
}));

// The component loads configuration data in an effect on mount; flush the
// mocked promise inside act() so state updates settle before assertions.
async function renderDoc() {
  const utils = render(<DocumentationContent />);
  await act(async () => {});
  return utils;
}

describe('DocumentationContent', () => {
  it('renders nav and content', async () => {
    await renderDoc();
    expect(screen.getAllByText('Documentation').length).toBeGreaterThanOrEqual(1);
  });

  it('does not use GitHub install URL (uses PyPI)', async () => {
    const { container } = await renderDoc();
    expect(container.innerHTML).not.toContain('git+https');
  });

  it('shows intro blurb with drop-in replacement and PyPI install', async () => {
    const { container } = await renderDoc();
    expect(container.textContent).toContain('drop-in replacement');
    expect(container.textContent).toContain('uv tool install policyengine-taxsim');
  });

  it('shows the section tabs', async () => {
    await renderDoc();
    [
      'Installation & Usage',
      'All Runners & CLI',
      'Variable Mappings',
      'Sample Datasets',
    ].forEach(label => {
      expect(
        screen.getAllByRole('button', { name: label }).length
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows separate installation and usage sections', async () => {
    const { container } = await renderDoc();
    // Installation card: the OS toggle is unique to that section
    expect(
      screen.getByRole('button', { name: 'macOS/Linux' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Windows' })).toBeInTheDocument();
    // Usage section intro
    expect(container.textContent).toContain(
      'Same input format, same output variables'
    );
  });

  it('shows all 6 language tabs in usage section', async () => {
    await renderDoc();
    ['CLI', 'Python', 'R', 'Stata', 'SAS', 'Julia'].forEach(tab => {
      expect(
        screen.getAllByRole('button', { name: tab }).length
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it('R tab shows R package install and auto-setup note', async () => {
    await renderDoc();
    const [rButton] = screen.getAllByRole('button', { name: 'R' });
    fireEvent.click(rButton);
    const codeBlocks = document.querySelectorAll('code');
    const hasAutoSetup = Array.from(codeBlocks).some(el =>
      el.textContent.includes('Python dependencies install automatically')
    );
    expect(hasAutoSetup).toBe(true);
  });

  it('All Runners section shows runners and CLI with stdin/stdout docs', async () => {
    await renderDoc();
    const [runnersTab] = screen.getAllByRole('button', {
      name: 'All Runners & CLI',
    });
    fireEvent.click(runnersTab);
    expect(screen.getAllByText('TaxsimRunner').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Command-line interface')).toBeInTheDocument();
    expect(
      screen.getAllByText(/reads from stdin and writes to stdout/).length
    ).toBeGreaterThanOrEqual(1);
  });

  it('Sample Datasets section links to Enhanced CPS sources', async () => {
    await renderDoc();
    const [datasetsTab] = screen.getAllByRole('button', {
      name: 'Sample Datasets',
    });
    fireEvent.click(datasetsTab);
    const ecpsLink = screen.getByRole('link', {
      name: /Enhanced Current Population Survey/,
    });
    expect(ecpsLink.getAttribute('href')).toBe(
      'https://policyengine.github.io/policyengine-us-data/'
    );
    const hfLink = screen.getByRole('link', { name: 'HuggingFace' });
    expect(hfLink.getAttribute('href')).toBe(
      'https://huggingface.co/policyengine/policyengine-us-data'
    );
  });

  it('Variable Mappings section renders the search box once config loads', async () => {
    await renderDoc();
    const [mappingsTab] = screen.getAllByRole('button', {
      name: 'Variable Mappings',
    });
    fireEvent.click(mappingsTab);
    expect(
      await screen.findByPlaceholderText('Search variables...')
    ).toBeInTheDocument();
  });
});
