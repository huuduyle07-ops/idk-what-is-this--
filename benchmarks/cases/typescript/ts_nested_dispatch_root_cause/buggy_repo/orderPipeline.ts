import { dispatch } from "./registry.ts";
import type { OrderLine } from "./pricing.ts";

export type OrderRequest = {
  kind: "checkout" | "refund";
  lines: OrderLine[];
};

// Top-level service. Routes the request through the registry, which then
// invokes the appropriate handler, which finally calls pricing. This file
// is plumbing only — no arithmetic here.
export function processOrder(request: OrderRequest): number {
  return dispatch(request.kind, { lines: request.lines });
}
