/**
 * GET /api/chat/history?arxiv_id=...
 *
 * Returns the persisted conversation for a paper. Cross-device sync is
 * automatic because there's exactly one shared conversation per paper
 * (no session_id namespacing) stored under KV key `chat:<arxiv_id>`.
 */

import { NextRequest, NextResponse } from "next/server";
import { kvGet, kvDel } from "@/lib/kv";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type ChatMessage = { role: "user" | "assistant"; content: string; ts: string };

function chatKey(arxivId: string): string {
  return `chat:${arxivId}`;
}

export async function GET(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  if (!arxivId)
    return NextResponse.json({ error: "arxiv_id required" }, { status: 400 });
  try {
    const messages = (await kvGet<ChatMessage[]>(chatKey(arxivId))) ?? [];
    return NextResponse.json({ messages });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message ?? String(err), messages: [] },
      { status: 500 },
    );
  }
}

/** DELETE /api/chat/history?arxiv_id=... — wipe the conversation. */
export async function DELETE(req: NextRequest) {
  const u = new URL(req.url);
  const arxivId = u.searchParams.get("arxiv_id");
  if (!arxivId)
    return NextResponse.json({ error: "arxiv_id required" }, { status: 400 });
  await kvDel(chatKey(arxivId));
  return NextResponse.json({ ok: true });
}
