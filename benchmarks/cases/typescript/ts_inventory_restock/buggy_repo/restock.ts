export function calculateRestockAmount(
  currentStock: number,
  reorderPoint: number,
  maxCapacity: number,
): number {
  // BUG: skips validation and always returns maxCapacity - currentStock.
  return maxCapacity - currentStock;
}
