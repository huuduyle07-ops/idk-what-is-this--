import type { EventPayload } from "./dispatcher.ts";

export function handleOrderPlaced(payload: EventPayload): number {
  return payload.balance - payload.amount;
}

export function handleRefund(payload: EventPayload): number {
  // BUG: refund should ADD the refunded amount back to the balance,
  // not subtract it. The dispatcher correctly routes "refund" here —
  // the defect is in this handler, not in the dispatcher.
  return payload.balance - payload.amount;
}

export function handleCancel(payload: EventPayload): number {
  return payload.balance;
}
