export function formatCurrency(amountCents: number, currency: string): string {
    const value = amountCents / 100;
    return `${currency} ${value.toFixed(2)}`;
}
