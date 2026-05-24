import { processOrder } from "./orderPipeline.ts";

function assertEqual(actual: number, expected: number, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function main(): void {
  // 2 keyboards @ $120 + 1 mouse @ $45 + 1 monitor @ $300 = $585.00 = 58500c
  const checkoutTotal = processOrder({
    kind: "checkout",
    lines: [
      { sku: "keyboard", unitPriceCents: 12000, qty: 2 },
      { sku: "mouse", unitPriceCents: 4500, qty: 1 },
      { sku: "monitor", unitPriceCents: 30000, qty: 1 },
    ],
  });
  assertEqual(
    checkoutTotal,
    58500,
    "checkout total for 2 keyboards + 1 mouse + 1 monitor",
  );

  // 3 keyboards @ $120 = $360.00 = 36000c — refund flows through the
  // SAME pricing helper as checkout, so a bug there breaks both paths.
  const refundTotal = processOrder({
    kind: "refund",
    lines: [
      { sku: "keyboard", unitPriceCents: 12000, qty: 3 },
    ],
  });
  assertEqual(refundTotal, 36000, "refund total for 3 keyboards");

  // Edge case: empty cart must remain 0.
  const emptyTotal = processOrder({
    kind: "checkout",
    lines: [],
  });
  assertEqual(emptyTotal, 0, "empty checkout total is zero");

  console.log("OK");
}

main();
