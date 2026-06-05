export type RawTicket = {
    id: string;
    status: string;
    title: string;
};

export type Ticket = {
    id: string;
    status: string;
    title: string;
};

export function normalizeTicket(row: RawTicket): Ticket {
    return {
        id: row.id,
        status: row.status.toLowerCase(),
        title: row.title.trim(),
    };
}
