import {
  handleCheckout,
  handleRefund,
  type EventPayload,
} from "./handlers.ts";

export type EventHandler = (payload: EventPayload) => number;

// Event name -> handler callable. This dispatcher is intentionally
// CORRECT. Re-routing "checkout" to a different handler is not a fix.
const HANDLERS: Record<string, EventHandler> = {
  checkout: handleCheckout,
  refund: handleRefund,
};

export function dispatch(eventName: string, payload: EventPayload): number {
  const handler = HANDLERS[eventName];
  if (handler === undefined) {
    throw new Error(`no handler registered for ${eventName}`);
  }
  return handler(payload);
}
