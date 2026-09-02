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
