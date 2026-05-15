/**
 * Thin wrapper around Upstash Redis.
 *
 * Vercel injects different env-var names depending on which integration
 * you used:
 *
 *   - Upstash marketplace (direct):       UPSTASH_REDIS_REST_URL / _TOKEN
 *   - Vercel's KV / new Storage product:  KV_REST_API_URL        / KV_REST_API_TOKEN
 *
 * We accept either pair, so whichever provisioning path you took on Vercel
 * just works. ``@upstash/redis``'s own ``Redis.fromEnv()`` only looks at
 * the first pair, so we construct the client explicitly with whichever
 * pair is present.
 *
 * For local dev WITHOUT a real Redis, we fall back to an in-memory Map.
 * Fine for prototyping (data lost on process restart); NOT fine in
 * serverless production — different invocations hit different Lambda
 * instances, so the Map looks like it forgets every write. The fallback is
 * announced via :func:`kvBackend` for debug.
 *
 * Key conventions:
 *    stars                       → JSON object { arxiv_id: { topic, note, ts } }
 *    hidden                      → JSON object { arxiv_id: { hidden_at } }
 *    chat:<arxiv_id>             → JSON array of { role, content, ts }
 *    chat-meta:<arxiv_id>        → JSON { last_message_at }
 */

import type { Redis } from "@upstash/redis";

type KVLike = {
  get<T = unknown>(key: string): Promise<T | null>;
  set(key: string, value: unknown, opts?: { ex?: number }): Promise<unknown>;
  del(...keys: string[]): Promise<number>;
  keys(pattern: string): Promise<string[]>;
};

type Creds = { url: string; token: string };

function resolveCreds(): Creds | null {
  const pairs: Array<[string | undefined, string | undefined]> = [
    [process.env.UPSTASH_REDIS_REST_URL, process.env.UPSTASH_REDIS_REST_TOKEN],
    [process.env.KV_REST_API_URL, process.env.KV_REST_API_TOKEN],
  ];
  for (const [url, token] of pairs) {
    if (url && token) return { url, token };
  }
  return null;
}

function hasRealKV(): boolean {
  return resolveCreds() !== null;
}

// --- in-memory fallback for local dev ---------------------------------------
// We deliberately use a module-level Map. Hot-reload in `next dev` can blow
// the module cache and reset state — that's fine for a dev fallback.

const _mem = new Map<string, { value: unknown; expiresAt?: number }>();

function _purge(): void {
  const now = Date.now();
  for (const [k, v] of _mem) {
    if (v.expiresAt && v.expiresAt < now) _mem.delete(k);
  }
}

const memKV: KVLike = {
  async get<T = unknown>(key: string): Promise<T | null> {
    _purge();
    const e = _mem.get(key);
    return (e?.value ?? null) as T | null;
  },
  async set(key: string, value: unknown, opts?: { ex?: number }): Promise<unknown> {
    const expiresAt = opts?.ex ? Date.now() + opts.ex * 1000 : undefined;
    _mem.set(key, { value, expiresAt });
    return "OK";
  },
  async del(...keys: string[]): Promise<number> {
    let n = 0;
    for (const k of keys) if (_mem.delete(k)) n += 1;
    return n;
  },
  async keys(pattern: string): Promise<string[]> {
    _purge();
    // Support only the simple glob shapes we actually use: "prefix:*"
    const star = pattern.indexOf("*");
    if (star === -1) return _mem.has(pattern) ? [pattern] : [];
    const prefix = pattern.slice(0, star);
    return Array.from(_mem.keys()).filter((k) => k.startsWith(prefix));
  },
};

// --- real Redis -------------------------------------------------------------
// Lazy-load so the dev fallback doesn't drag in @upstash/redis when env isn't
// set.

let _realRedis: Redis | null = null;
async function realRedis(): Promise<KVLike> {
  if (_realRedis) return _realRedis as unknown as KVLike;
  const creds = resolveCreds();
  if (!creds) throw new Error("No Redis credentials present");
  const { Redis } = await import("@upstash/redis");
  // Construct explicitly so we work with either env-var pair — fromEnv()
  // only knows about UPSTASH_REDIS_REST_*.
  _realRedis = new Redis({ url: creds.url, token: creds.token });
  return _realRedis as unknown as KVLike;
}

// --- public surface ---------------------------------------------------------

export async function kvGet<T = unknown>(key: string): Promise<T | null> {
  if (hasRealKV()) {
    const r = await realRedis();
    return r.get<T>(key);
  }
  return memKV.get<T>(key);
}

export async function kvSet(
  key: string,
  value: unknown,
  opts?: { ttlSeconds?: number },
): Promise<void> {
  const kvOpts = opts?.ttlSeconds ? { ex: opts.ttlSeconds } : undefined;
  if (hasRealKV()) {
    const r = await realRedis();
    await r.set(key, value, kvOpts);
    return;
  }
  await memKV.set(key, value, kvOpts);
}

export async function kvDel(key: string): Promise<void> {
  if (hasRealKV()) {
    const r = await realRedis();
    await r.del(key);
    return;
  }
  await memKV.del(key);
}

export async function kvListKeys(pattern: string): Promise<string[]> {
  if (hasRealKV()) {
    const r = await realRedis();
    return r.keys(pattern);
  }
  return memKV.keys(pattern);
}

/** Surface which backend is live (for debug pages / banners). */
export function kvBackend(): "upstash-redis" | "memory" {
  return hasRealKV() ? "upstash-redis" : "memory";
}
