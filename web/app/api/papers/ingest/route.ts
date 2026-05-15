/**
 * POST /api/papers/ingest
 *
 * Body: { url: string, topic?: string }
 *
 * Flow:
 *  1. Parse the arxiv id (also accepts a bare id).
 *  2. If we already have a JSON file at data/analyses/<id>.json → respond
 *     `{ status: "already_analysed", arxiv_id }` so the client redirects.
 *  3. Otherwise dispatch analyse-one.yml on GitHub. The workflow writes
 *     the JSON file, commits it, pushes; Vercel auto-redeploys and the
 *     status poll will then see the file appear.
 */

import { NextRequest, NextResponse } from "next/server";
import { analysisExists } from "@/lib/data-reader";
import { parseArxivId } from "@/lib/arxiv-id";
import { dispatchWorkflow } from "@/lib/github";

export const runtime = "nodejs";

// GET is used by the login page as a "do I have auth?" probe.
export async function GET() {
  return NextResponse.json({ ok: true });
}

export async function POST(req: NextRequest) {
  let body: { url?: string; topic?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const arxivId = parseArxivId(body.url ?? "");
  if (!arxivId) {
    return NextResponse.json(
      { error: "could not extract arXiv id from input" },
      { status: 400 },
    );
  }

  // Cheap filesystem check — already-analysed papers shouldn't re-burn LLM
  // tokens. The user usually wants to see the existing report anyway.
  if (await analysisExists(arxivId)) {
    return NextResponse.json({ status: "already_analysed", arxiv_id: arxivId });
  }

  try {
    await dispatchWorkflow({
      workflowFile: "analyse-one.yml",
      inputs: { arxiv_id: arxivId, topic: body.topic ?? "" },
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: `workflow_dispatch failed: ${err.message ?? String(err)}` },
      { status: 502 },
    );
  }

  return NextResponse.json(
    { status: "dispatched", arxiv_id: arxivId },
    { status: 202 },
  );
}
