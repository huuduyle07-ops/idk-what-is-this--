import type { Ticket } from "./normalizer.ts";

export function openTicketSummary(tickets: Ticket[]): string {
    const openCount = tickets.filter((ticket) => ticket.status === "open").length;
    return `Open tickets: ${openCount}`;
}
