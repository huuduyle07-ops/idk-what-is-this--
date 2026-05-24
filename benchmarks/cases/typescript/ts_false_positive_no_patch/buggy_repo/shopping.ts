export function calculateCartTotal(prices: number[]): number {
  // Correct implementation. Sums all line items.
  return prices.reduce((sum, price) => sum + price, 0);
}
