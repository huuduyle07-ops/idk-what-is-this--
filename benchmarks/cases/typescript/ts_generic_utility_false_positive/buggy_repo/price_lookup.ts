import { formatCurrency } from "./format.ts";

const PRICES_CENTS: Record<string, number> = {
    "widget": 1999,
    "gadget": 4999,
    "doohickey": 799,
};

export function getProductPrice(productId: string): string {
    const cents = PRICES_CENTS[productId] ?? 0;
    // BUG: divides by 100 before passing to formatCurrency, which divides again
    return formatCurrency(cents / 100, "USD");
}
