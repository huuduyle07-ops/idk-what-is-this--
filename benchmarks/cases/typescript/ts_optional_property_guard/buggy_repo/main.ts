import { displayEmail } from "./userSummary.ts";

function assertEqual(actual: string, expected: string, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function main(): void {
  assertEqual(
    displayEmail({ profile: { email: " PERSON@Example.COM " } }),
    "person@example.com",
    "profile email should be normalized",
  );
  assertEqual(
    displayEmail({ fallbackEmail: " FALLBACK@Example.COM " }),
    "fallback@example.com",
    "missing profile should use fallback",
  );
  assertEqual(
    displayEmail({ profile: null, fallbackEmail: "NULLPROFILE@Example.COM" }),
    "nullprofile@example.com",
    "null profile should use fallback",
  );
  assertEqual(
    displayEmail({ profile: { email: "   " }, fallbackEmail: "backup@example.com" }),
    "backup@example.com",
    "blank profile email should use fallback",
  );
  assertEqual(displayEmail({ profile: {} }), "unknown", "missing emails should be unknown");

  console.log("OK");
}

main();
