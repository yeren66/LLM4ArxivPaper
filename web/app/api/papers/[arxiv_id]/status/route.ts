/**
 * GET /api/papers/<arxiv_id>/status
 *
 * Polled by /submit while waiting for the analyse-one workflow to finish.
 * Returns { ready } based on whether `data/analyses/<arxiv_id>.json` exists
 * yet. Note Vercel auto-redeploys when the workflow pushes the new file, so
 * the file becomes visible to this function after the redeploy (typically
 * ~30s after the git push).
 */

import { NextRequest, NextResponse } from "next/server";
import { analysisExists } from "@/lib/data-reader";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { arxiv_id: string } },
) {
  const arxivId = decodeURIComponent(params.arxiv_id);
  try {
    const ready = await analysisExists(arxivId);
    return NextResponse.json(
      { arxiv_id: arxivId, ready },
      { headers: { "cache-control": "no-store" } },
    );
  } catch (err: any) {
    return NextResponse.json(
      { arxiv_id: arxivId, ready: false, error: err.message ?? String(err) },
      { status: 500 },
    );
  }
}
