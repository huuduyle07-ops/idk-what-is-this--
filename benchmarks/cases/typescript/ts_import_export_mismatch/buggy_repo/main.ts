import { makeSlug } from "./slug.ts";

function assertEqual(actual: string, expected: string, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function main(): void {
  assertEqual(makeSlug(" Hello World "), "hello-world", "words should be hyphenated");
  assertEqual(makeSlug("Ship  It!!"), "ship-it", "punctuation should be removed");
  assertEqual(makeSlug("Already-slugged"), "already-slugged", "existing hyphens should remain");

  console.log("OK");
}

main();
