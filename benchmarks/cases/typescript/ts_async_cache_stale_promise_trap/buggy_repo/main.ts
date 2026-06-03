import { cachedFetch, clearCache } from "./cache.ts";

async function main(): Promise<void> {
    let callCount = 0;
    const fetcher = async (k: string): Promise<string> => {
        callCount++;
        return `value_${k}`;
    };

    clearCache();
    callCount = 0;

    // first call: must fetch
    const r1 = await cachedFetch("foo", fetcher);
    if (r1 !== "value_foo") throw new Error(`r1: expected 'value_foo', got '${r1}'`);
    if (callCount !== 1) throw new Error(`after first call: expected 1 fetch, got ${callCount}`);

    // second call: must hit the cache, not call fetcher again
    const r2 = await cachedFetch("foo", fetcher);
    if (r2 !== "value_foo") throw new Error(`r2: expected 'value_foo', got '${r2}'`);
    if (callCount !== 1) throw new Error(`after second call: expected 1 fetch (cache hit), got ${callCount}`);

    // different key: must fetch again
    const r3 = await cachedFetch("bar", fetcher);
    if (r3 !== "value_bar") throw new Error(`r3: expected 'value_bar', got '${r3}'`);
    if (callCount !== 2) throw new Error(`after third call (new key): expected 2 fetches, got ${callCount}`);

    console.log("OK");
}

main().catch(err => {
    process.stderr.write(`FAIL: ${err.message}\n`);
    process.exit(1);
});
