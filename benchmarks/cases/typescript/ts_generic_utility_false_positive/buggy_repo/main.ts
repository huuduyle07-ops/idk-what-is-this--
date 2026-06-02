import { getProductPrice } from "./price_lookup.ts";

function assertEqual(actual: string, expected: string, msg: string): void {
    if (actual !== expected) {
        throw new Error(`${msg}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

assertEqual(getProductPrice("widget"), "USD 19.99", "widget price");
assertEqual(getProductPrice("gadget"), "USD 49.99", "gadget price");
assertEqual(getProductPrice("doohickey"), "USD 7.99", "doohickey price");

console.log("OK");
