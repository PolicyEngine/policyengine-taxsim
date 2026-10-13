import { describe, expect, it } from 'vitest';
import { formatInputValue } from '../formatters';

describe('formatInputValue mstat labels', () => {
  it('labels the TAXSIM marital-status codes the emulator supports', () => {
    expect(formatInputValue('mstat', 1)).toBe('Single');
    expect(formatInputValue('mstat', 2)).toBe('Married Filing Jointly');
    expect(formatInputValue('mstat', 6)).toBe('Married Filing Separately');
  });

  it('falls back to the raw code for other values', () => {
    expect(formatInputValue('mstat', 8)).toBe('8');
  });
});
