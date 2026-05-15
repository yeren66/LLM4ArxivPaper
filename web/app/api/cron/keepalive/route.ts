/**
 * GET /api/cron/keepalive
 *
 * Hit on schedule by Vercel Cron. Triggers `weekly-pipeline.yml` via
 * GitHub's workflow_dispatch API, which makes the GH Actions run (and the
 * heartbeat commit it produces) restart the 60-day inactivity clock.
 *
 * Vercel sets `x-vercel-cron-signature` automatically when invoking cron
 * routes; we additionally accept a shared CRON_SECRET so the route can be
 * curl'd manually for testing.
 */

import { NextRequest, NextResponse } from "next/server";
import { dispatchWorkflow } from "@/lib/github";

export const runtime = "nodejs";

function authorised(req: NextRequest): boolean {
  // Vercel cron triggers carry this header.
  if (req.headers.get("x-vercel-cron")) return true;

  // Allow `Authorization: Bearer <CRON_SECRET>` for manual / curl runs.
  const secret = process.env.CRON_SECRET;
  if (!secret) return true; // no secret configured → don't fight the operator
  const auth = req.headers.get("authorization");
  if (!auth) return false;
  return auth === `Bearer ${secret}`;
}

export async function GET(req: NextRequest) {
  if (!authorised(req)) {
    return NextResponse.json({ error: "unauthorised" }, { status: 401 });
  }
  try {
    await dispatchWorkflow({ workflowFile: "weekly-pipeline.yml" });
  } catch (err: any) {
    return NextResponse.json(
      { ok: false, error: err.message ?? String(err) },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true, dispatched: "weekly-pipeline.yml" });
}
