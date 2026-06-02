import { getDisplayPrice } from "./index.ts";

function assertEqual(actual: string, expected: string, msg: string): void {
    if (actual !== expected) {
        throw new Error(msg + ": expected " + JSON.stringify(expected) + ", got " + JSON.stringify(actual));
    }
}

assertEqual(getDisplayPrice(999), "$9.99", "cents to dollars");
assertEqual(getDisplayPrice(100), "$1.00", "one dollar");
assertEqual(getDisplayPrice(0), "$0.00", "zero");

console.log("OK");
