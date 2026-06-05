import { normalizeTicket } from "./normalizer.ts";
import type { RawTicket } from "./normalizer.ts";
import { openTicketSummary } from "./display.ts";

function assertEqual(actual: string, expected: string, message: string): void {
    if (actual !== expected) {
        throw new Error(`${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

const rows: RawTicket[] = [
    { id: "T-1", status: "open", title: " checkout broken " },
    { id: "T-2", status: " OPEN ", title: "invoice export" },
    { id: "T-3", status: "closed", title: "resolved" },
];

const tickets = rows.map(normalizeTicket);

assertEqual(openTicketSummary(tickets), "Open tickets: 2", "open ticket count");
assertEqual(tickets[1].title, "invoice export", "title trimming still works");

console.log("OK");
