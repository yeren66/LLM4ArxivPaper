/**
 * GET /api/kv-status
 *
 * Tiny diagnostic for "stars / hide silently don't persist": reports which
 * Redis env-var pair was detected and does a round-trip write/read against
 * a throwaway key. If it returns `backend: "memory"`, no Redis env vars are
 * reaching the deployment — stars and hide will appear to work in the same
 * request but vanish on the next one (different Lambda instance).
 *
 * Read-only; no auth required (returns no secrets, just booleans).
 */

import { NextResponse } from "next/server";
import { kvGet, kvSet, kvDel, kvBackend } from "@/lib/kv";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const present = {
    UPSTASH_REDIS_REST_URL: Boolean(process.env.UPSTASH_REDIS_REST_URL),
    UPSTASH_REDIS_REST_TOKEN: Boolean(process.env.UPSTASH_REDIS_REST_TOKEN),
    KV_REST_API_URL: Boolean(process.env.KV_REST_API_URL),
    KV_REST_API_TOKEN: Boolean(process.env.KV_REST_API_TOKEN),
  };
  const backend = kvBackend();

  let roundtrip: { ok: boolean; error?: string } = { ok: false };
  const probeKey = "kv-status-probe";
  try {
    const stamp = new Date().toISOString();
    await kvSet(probeKey, { stamp }, { ttlSeconds: 60 });
    const got = await kvGet<{ stamp: string }>(probeKey);
    roundtrip = { ok: got?.stamp === stamp };
    await kvDel(probeKey).catch(() => {});
  } catch (err: any) {
    roundtrip = { ok: false, error: err?.message ?? String(err) };
  }

  return NextResponse.json({
    backend,
    env_present: present,
    roundtrip,
    hint:
      backend === "memory"
        ? "No Redis credentials detected. On Vercel, install the Upstash Redis integration (Storage → Marketplace) or set UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN (or KV_REST_API_URL / KV_REST_API_TOKEN) in the project's Environment Variables, then redeploy."
        : "Redis backend live. Stars and hide should persist.",
  });
}
