/**
 * Annotations CRUD. KV key: `annotations:<arxiv_id>`.
 *
 *   GET    /api/annotations?arxiv_id=X            → { annotations: [...] }
 *   POST   /api/annotations { arxiv_id, stage, quote, note, id? }
 *            - omit `id` to create; include it to update in place
 *   DELETE /api/annotations?arxiv_id=X&id=Y
 *
 * Auth: middleware gates POST/DELETE via the ADMIN_TOKEN cookie. We follow
 * the stars/hide pattern — list reads are public (anyone visiting the paper
 * page sees the same single-user notes).
 */
import { NextRequest, NextResponse } from "next/server";
import {
  Annotation,
  ANNOTATION_STAGES,
  AnnotationStage,
  getAnnotations,
  saveAnnotations,
} from "@/lib/annotations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function badRequest(msg: string) {
  return NextResponse.json({ error: msg }, { status: 400 });
}

export async function GET(req: NextRequest) {
  const arxivId = new URL(req.url).searchParams.get("arxiv_id");
  if (!arxivId) return badRequest("arxiv_id required");
  const map = await getAnnotations(arxivId);
  // Stable sort: newest first.
  const items = Object.values(map).sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  );
  return NextResponse.json({ annotations: items });
}

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as Partial<Annotation>;
  const arxivId = body.arxiv_id;
  if (!arxivId) return badRequest("arxiv_id required");
  const stage = body.stage as AnnotationStage | undefined;
  if (!stage || !ANNOTATION_STAGES.has(stage)) return badRequest("invalid stage");
  const quote = (body.quote ?? "").trim();
  if (!quote) return badRequest("quote required");
  const note = (body.note ?? "").trim();

  const map = await getAnnotations(arxivId);
  const now = new Date().toISOString();
  const id = body.id && map[body.id] ? body.id : cryptoId();
  const existing = map[id];
  map[id] = {
    id,
    arxiv_id: arxivId,
    stage,
    quote,
    note,
    created_at: existing?.created_at ?? now,
    updated_at: now,
  };
  await saveAnnotations(arxivId, map);
  return NextResponse.json({ ok: true, annotation: map[id] });
}

export async function DELETE(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  const id = u.searchParams.get("id");
  if (!arxivId || !id) return badRequest("arxiv_id and id required");
  const map = await getAnnotations(arxivId);
  if (!map[id]) return NextResponse.json({ ok: true, missing: true });
  delete map[id];
  await saveAnnotations(arxivId, map);
  return NextResponse.json({ ok: true });
}

function cryptoId(): string {
  // `crypto.randomUUID` is in the global scope on Node 18+ and Edge.
  // Fallback for the rare case it's missing (older runtimes in dev).
  try {
    return crypto.randomUUID();
  } catch {
    return `a_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  }
}
