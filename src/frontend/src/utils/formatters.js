/**
 * Monetary and Numeric Formatters
 * Adheres to luxury styling and strict 2-decimal ceiling rounding for SGD display (S$0.00).
 */

/**
 * Formats a monetary cost in SGD with strict 2-decimal ceiling rounding.
 * e.g., 0.041 -> S$0.05, 0.001 -> S$0.01, 0 -> S$0.00
 *
 * @param {number|string|null|undefined} costSgd - Cost in SGD
 * @param {number|string|null|undefined} [costUsd] - Optional fallback cost in USD if SGD is missing
 * @param {number} [exchangeRate=1.35] - USD to SGD conversion rate fallback
 * @returns {string} Formatted string, e.g. "S$0.05"
 */
export function formatSpendSGD(costSgd, costUsd, exchangeRate = 1.35) {
  let val = costSgd !== undefined && costSgd !== null ? Number(costSgd) : NaN;

  if (isNaN(val) || val <= 0) {
    if (costUsd !== undefined && costUsd !== null) {
      const usdVal = Number(costUsd);
      if (!isNaN(usdVal) && usdVal > 0) {
        val = usdVal * exchangeRate;
      }
    }
  }

  if (isNaN(val) || val <= 0) {
    return 'S$0.00';
  }

  // Ceiling round to 2 decimal places: Math.ceil(x * 100) / 100
  const roundedCeil = Math.ceil(val * 100) / 100;
  return `S$${roundedCeil.toFixed(2)}`;
}

/**
 * Formats token counts cleanly with comma separators.
 * @param {number|string|null|undefined} tokens
 * @returns {string} e.g. "1,250"
 */
export function formatTokens(tokens) {
  const count = Number(tokens);
  if (isNaN(count) || count <= 0) return '0';
  return count.toLocaleString('en-US');
}

/**
 * Formats a UTC ISO date string into GMT+8 date, time, and timezone.
 * e.g. "2026-08-24T00:00:00Z" -> "24 Aug 2026, 08:00:00 GMT+8"
 *
 * @param {string|Date|null|undefined} dateInput - ISO string or Date object in UTC
 * @param {Intl.DateTimeFormatOptions} [options] - Optional custom overrides for Intl.DateTimeFormat
 * @returns {string} Formatted date time string with GMT+8 timezone
 */
export function formatDateTimeGMT8(dateInput, options = {}) {
  if (!dateInput) return '';
  try {
    let str = typeof dateInput === 'string' ? dateInput.trim() : dateInput;
    if (typeof str === 'string' && !str.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(str)) {
      str += 'Z';
    }
    const d = new Date(str);
    if (isNaN(d.getTime())) return '';

    return new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Singapore',
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZoneName: 'shortOffset',
      ...options,
    }).format(d);
  } catch (err) {
    console.error('Failed to format GMT+8 date:', err);
    return '';
  }
}
