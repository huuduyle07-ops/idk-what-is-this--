import { dispatch } from "./dispatcher.ts";

function assertEqual(actual: number, expected: number, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function main(): void {
  const orderResult = dispatch("order_placed", {
    balance: 100,
    amount: 30,
  });
  assertEqual(orderResult, 70, "order_placed should subtract amount from balance");

  const refundResult = dispatch("refund", {
    balance: 70,
    amount: 25,
  });
  assertEqual(refundResult, 95, "refund should ADD amount back to balance");

  const cancelResult = dispatch("cancel", {
    balance: 95,
    amount: 0,
  });
  assertEqual(cancelResult, 95, "cancel should leave balance unchanged");

  console.log("OK");
}

main();
