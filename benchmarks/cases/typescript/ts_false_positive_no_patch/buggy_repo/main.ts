import { calculateCartTotal } from "./shopping.ts";

function assertEqual(actual: number, expected: number, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function main(): void {
  // All assertions already pass — the code under test is correct.
  assertEqual(calculateCartTotal([]), 0, "empty cart");
  assertEqual(calculateCartTotal([10]), 10, "single-item cart");
  assertEqual(calculateCartTotal([1.5, 2.5, 3]), 7, "three-item cart");
  assertEqual(
    calculateCartTotal([100, 200, 300]),
    600,
    "large cart",
  );
  console.log("OK");
}

main();
