const store = new Map<string, string>();

export async function cachedFetch(
    key: string,
    fetcher: (k: string) => Promise<string>,
): Promise<string> {
    const hit = store.get(key);
    if (hit !== undefined) return hit;
    const result = await fetcher(key);
    // BUG: stores result under wrong key (uppercase) — cache lookup uses original key
    store.set(key.toUpperCase(), result);
    return result;
}

export function clearCache(): void {
    store.clear();
}
