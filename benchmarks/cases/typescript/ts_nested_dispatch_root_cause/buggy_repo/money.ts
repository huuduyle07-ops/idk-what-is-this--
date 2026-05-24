// Shared money utilities. Imported in many places (registry/handlers/pricing
// all transitively use it), so this module looks central by graph weight.
// It is intentionally CORRECT — do not modify it.

export function toCents(dollars: number): number {
  return Math.round(dollars * 100);
}

export function addCents(a: number, b: number): number {
  return a + b;
}

export function multiplyCents(unitCents: number, count: number): number {
  return unitCents * count;
}

export function formatCents(cents: number): string {
  const dollars = Math.floor(cents / 100);
  const rem = cents % 100;
  return `$${dollars}.${rem.toString().padStart(2, "0")}`;
}
