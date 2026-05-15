/**
 * Hide CRUD. Soft-deletes a paper from the user's default views without
 * touching ``data/analyses/<id>.json`` — analyses are expensive to produce
 * and dropping the JSON would be irreversible. Hidden papers are filtered
 * out of the All / This Week / Starred home tabs and surface only in the
 * dedicated "Hidden" tab, where they can be restored.
 *
 * Live state lives in Upstash Redis (key: `hidden`). A daily Vercel cron
 * snapshots this into `data/hidden.json` (when ARCHIVE_HIDDEN is enabled)
 * for git-based backup — same pattern as stars.
 *
 *   GET    /api/hide                      → list all
 *   GET    /api/hide?arxiv_id=X           → { hidden: boolean }
 *   POST   /api/hide  { arxiv_id }        → hide
 *   DELETE /api/hide?arxiv_id=X           → restore
 *
 * Auth: middleware gates this route prefix; only ADMIN_TOKEN cookie gets in.
 */

import { NextRequest, NextResponse } from "next/server";
import { kvGet, kvSet } from "@/lib/kv";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type HiddenRecord = { hidden_at: string };
type HiddenMap = Record<string, HiddenRecord>;

const HIDDEN_KEY = "hidden";

async function loadHidden(): Promise<HiddenMap> {
  return (await kvGet<HiddenMap>(HIDDEN_KEY)) ?? {};
}

async function saveHidden(map: HiddenMap): Promise<void> {
  await kvSet(HIDDEN_KEY, map);
}

export async function GET(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  const hidden = await loadHidden();
  if (!arxivId) {
    return NextResponse.json({
      count: Object.keys(hidden).length,
      hidden: Object.entries(hidden).map(([id, v]) => ({ arxiv_id: id, ...v })),
    });
  }
  return NextResponse.json({ arxiv_id: arxivId, hidden: Boolean(hidden[arxivId]) });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({} as any));
  const arxivId: string | undefined = body?.arxiv_id;
  if (!arxivId)
    return NextResponse.json({ error: "arxiv_id required" }, { status: 400 });
  const hidden = await loadHidden();
  hidden[arxivId] = { hidden_at: new Date().toISOString() };
  await saveHidden(hidden);
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  if (!arxivId)
    return NextResponse.json({ error: "arxiv_id required" }, { status: 400 });
  const hidden = await loadHidden();
  delete hidden[arxivId];
  await saveHidden(hidden);
  return NextResponse.json({ ok: true });
}
