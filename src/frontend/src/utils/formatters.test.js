import { describe, it, expect } from 'vitest';
import { formatSpendSGD, formatTokens, formatDateTimeGMT8 } from './formatters';

describe('formatters', () => {
  describe('formatSpendSGD', () => {
    it('applies ceiling rounding to 2 decimal places for SGD', () => {
      expect(formatSpendSGD(0.041)).toBe('S$0.05');
      expect(formatSpendSGD(0.001)).toBe('S$0.01');
      expect(formatSpendSGD(0)).toBe('S$0.00');
    });

    it('falls back to USD conversion if SGD is missing', () => {
      // 0.05 * 1.35 = 0.0675 -> ceiling 0.07
      expect(formatSpendSGD(null, 0.05, 1.35)).toBe('S$0.07');
    });
  });

  describe('formatTokens', () => {
    it('formats numbers with commas', () => {
      expect(formatTokens(1250)).toBe('1,250');
      expect(formatTokens(0)).toBe('0');
      expect(formatTokens(null)).toBe('0');
    });
  });

  describe('formatDateTimeGMT8', () => {
    it('correctly converts UTC ISO string with Z to GMT+8 date, time, and timezone', () => {
      const result = formatDateTimeGMT8('2026-08-24T00:00:00Z');
      expect(result).toBe('24 Aug 2026, 08:00:00 GMT+8');
    });

    it('correctly converts UTC ISO string with +00:00 offset to GMT+8', () => {
      const result = formatDateTimeGMT8('2026-10-01T12:35:58.123456+00:00');
      expect(result).toBe('01 Oct 2026, 20:35:58 GMT+8');
    });

    it('handles timestamp already with +08:00 offset', () => {
      const result = formatDateTimeGMT8('2026-10-01T20:35:58+08:00');
      expect(result).toBe('01 Oct 2026, 20:35:58 GMT+8');
    });

    it('handles naive ISO string without timezone indicator by treating as UTC', () => {
      const result = formatDateTimeGMT8('2026-08-24T00:00:00');
      expect(result).toBe('24 Aug 2026, 08:00:00 GMT+8');
    });

    it('returns empty string for null, undefined, or empty input', () => {
      expect(formatDateTimeGMT8(null)).toBe('');
      expect(formatDateTimeGMT8(undefined)).toBe('');
      expect(formatDateTimeGMT8('')).toBe('');
    });

    it('returns empty string for invalid date input', () => {
      expect(formatDateTimeGMT8('not-a-valid-date')).toBe('');
    });
  });
});
