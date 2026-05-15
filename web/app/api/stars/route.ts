/**
 * Stars CRUD. Live state lives in Upstash Redis (key: `stars`). A daily
 * Vercel cron snapshots this into `data/stars.json` for git-based backup.
 *
 *   GET  /api/stars?arxiv_id=X            → { starred: boolean }
 *   GET  /api/stars?arxiv_id=X&add=1      → toggle on, redirect to paper page
 *   GET  /api/stars                       → list all
 *   POST /api/stars { arxiv_id, topic?, note? }
 *   DELETE /api/stars?arxiv_id=X
 *
 * Auth: middleware gates this route prefix; only ADMIN_TOKEN cookie gets in.
 */

import { NextRequest, NextResponse } from "next/server";
import { kvGet, kvSet } from "@/lib/kv";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type StarRecord = { topic?: string; note?: string; starred_at: string };
type StarsMap = Record<string, StarRecord>;

const STARS_KEY = "stars";

async function loadStars(): Promise<StarsMap> {
  return (await kvGet<StarsMap>(STARS_KEY)) ?? {};
}

async function saveStars(stars: StarsMap): Promise<void> {
  await kvSet(STARS_KEY, stars);
}

export async function GET(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  const stars = await loadStars();

  if (!arxivId) {
    // List mode — handy for debug, also used by the admin panel.
    return NextResponse.json({
      count: Object.keys(stars).length,
      stars: Object.entries(stars).map(([id, v]) => ({ arxiv_id: id, ...v })),
    });
  }

  if (u.searchParams.get("add") === "1") {
    const topic = u.searchParams.get("topic") ?? undefined;
    stars[arxivId] = { topic, starred_at: new Date().toISOString() };
    await saveStars(stars);
    return NextResponse.redirect(
      new URL(`/papers/${encodeURIComponent(arxivId)}`, req.url),
    );
  }

  return NextResponse.json({ arxiv_id: arxivId, starred: Boolean(stars[arxivId]) });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({} as any));
  const arxivId: string | undefined = body?.arxiv_id;
  if (!arxivId)
    return NextResponse.json({ error: "arxiv_id required" }, { status: 400 });
  const stars = await loadStars();
  stars[arxivId] = {
    topic: body.topic ?? stars[arxivId]?.topic,
    note: body.note ?? stars[arxivId]?.note,
    starred_at: stars[arxivId]?.starred_at ?? new Date().toISOString(),
  };
  await saveStars(stars);
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  if (!arxivId)
    return NextResponse.json({ error: "arxiv_id required" }, { status: 400 });
  const stars = await loadStars();
  delete stars[arxivId];
  await saveStars(stars);
  return NextResponse.json({ ok: true });
}
