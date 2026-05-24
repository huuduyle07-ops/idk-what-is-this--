import {
  handleCancel,
  handleOrderPlaced,
  handleRefund,
} from "./handlers.ts";

export type EventPayload = {
  balance: number;
  amount: number;
};

export type EventHandler = (payload: EventPayload) => number;

// Event name -> handler callable. Adding/removing entries here only changes
// routing; the actual event logic lives inside each handler.
const HANDLERS: Record<string, EventHandler> = {
  order_placed: handleOrderPlaced,
  refund: handleRefund,
  cancel: handleCancel,
};

export function dispatch(eventName: string, payload: EventPayload): number {
  const handler = HANDLERS[eventName];
  if (handler === undefined) {
    throw new Error(`no handler registered for ${eventName}`);
  }
  return handler(payload);
}
