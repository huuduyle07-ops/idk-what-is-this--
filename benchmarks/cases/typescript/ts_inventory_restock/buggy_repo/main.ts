import { calculateRestockAmount } from "./restock.ts";
import { getMaxCapacity } from "./products.ts";

function assertEqual(actual: number, expected: number, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function assertThrows(fn: () => void, message: string): void {
  try {
    fn();
  } catch (e) {
    return;
  }
  throw new Error(message);
}

function main(): void {
  const widgetMax = getMaxCapacity("widget");

  assertEqual(
    calculateRestockAmount(5, 10, widgetMax),
    widgetMax - 5,
    "below reorder point should restock to max",
  );
  assertEqual(
    calculateRestockAmount(10, 10, widgetMax),
    0,
    "at reorder point should not restock",
  );
  assertEqual(
    calculateRestockAmount(widgetMax, 10, widgetMax),
    0,
    "at max capacity should not restock",
  );

  assertThrows(
    () => calculateRestockAmount(-1, 10, widgetMax),
    "negative currentStock should fail",
  );
  assertThrows(
    () => calculateRestockAmount(5, -10, widgetMax),
    "negative reorderPoint should fail",
  );
  assertThrows(
    () => calculateRestockAmount(5, 10, 0),
    "non-positive maxCapacity should fail",
  );
  assertThrows(
    () => calculateRestockAmount(5, 60, widgetMax),
    "reorderPoint > maxCapacity should fail",
  );

  console.log("OK");
}

main();
