import { calculateOrderTotal, type OrderLine } from "./pricing.ts";

export type EventPayload = {
  lines: OrderLine[];
};

// Thin pass-through handlers. They route the registered event to the
// pricing helper. Both call the SAME calculateOrderTotal — so a defect in
// pricing.ts surfaces through every handler, and patching one handler
// would not fix the other. The handlers themselves are correct.
export function handleCheckout(payload: EventPayload): number {
  return calculateOrderTotal(payload.lines);
}

export function handleRefund(payload: EventPayload): number {
  return calculateOrderTotal(payload.lines);
}
