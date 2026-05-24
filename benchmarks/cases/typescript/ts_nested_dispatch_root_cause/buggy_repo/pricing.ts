import { addCents } from "./money.ts";

export type OrderLine = {
  sku: string;
  unitPriceCents: number;
  qty: number;
};

export function calculateOrderTotal(lines: OrderLine[]): number {
  let total = 0;
  for (const line of lines) {
    // BUG: ignores line.qty. Should multiply unitPriceCents by qty before
    // adding. money.multiplyCents already exists for exactly this purpose,
    // but this loop forgets to call it.
    total = addCents(total, line.unitPriceCents);
  }
  return total;
}
