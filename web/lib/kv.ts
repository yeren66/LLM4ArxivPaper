/**
 * Thin wrapper around Upstash Redis (the new home for what used to be
 * "Vercel KV"). When the Upstash integration is installed on the Vercel
 * project, env vars are auto-injected:
 *
 *    UPSTASH_REDIS_REST_URL
 *    UPSTASH_REDIS_REST_TOKEN
 *
 * For local dev WITHOUT a real Redis (the common case while iterating), we
 * fall back to an in-memory `Map`. This keeps the dev loop friction-free.
 * Data is lost on process restart — acceptable for prototyping.
 *
 * Key conventions:
 *    stars                       → JSON object { arxiv_id: { topic, note, ts } }
 *    chat:<arxiv_id>             → JSON array of { role, content, ts }
 *    chat-meta:<arxiv_id>        → JSON { last_message_at }
 *    rate-limit:<ip>:<yyyymmdd>  → integer counter (planned, UX5)
 */

import type { Redis } from "@upstash/redis";

type KVLike = {
  get<T = unknown>(key: string): Promise<T | null>;
  set(key: string, value: unknown, opts?: { ex?: number }): Promise<unknown>;
  del(...keys: string[]): Promise<number>;
  keys(pattern: string): Promise<string[]>;
};

function hasRealKV(): boolean {
  return Boolean(
    process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN,
  );
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
  const { Redis } = await import("@upstash/redis");
  _realRedis = Redis.fromEnv();
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
