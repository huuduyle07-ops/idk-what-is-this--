// BUG: import path not updated after format.ts was renamed from pricing.ts during migration
import { formatPrice } from "./pricing.ts";

export function getDisplayPrice(productCents: number): string {
    return formatPrice(productCents);
}
