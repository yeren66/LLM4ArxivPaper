/**
 * GET /api/cron/archive-to-git
 *
 * Daily Vercel cron. Snapshots all live KV state (stars + chats) into
 * the git repo so we have a durable backup and an audit log of changes.
 *
 * Only commits files that **actually changed**; if nobody starred or chatted
 * since last run, this is a no-op (zero new commits).
 *
 * Auth: Vercel automatically attaches `x-vercel-cron` on scheduled invocations.
 *       For manual curl-testing, set CRON_SECRET and pass `Authorization: Bearer …`.
 */

import { NextRequest, NextResponse } from "next/server";
import { kvGet, kvListKeys } from "@/lib/kv";
import { writeIfChanged } from "@/lib/github-write";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function authorised(req: NextRequest): boolean {
  if (req.headers.get("x-vercel-cron")) return true;
  const secret = process.env.CRON_SECRET;
  if (!secret) return true; // unconfigured = allow (mostly for local dev)
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

// Which KV state gets snapshotted into the (possibly public) git repo.
//
//   ARCHIVE_STARS  default TRUE  — "papers I found interesting" is low
//                                  sensitivity and the git backup is useful.
//   ARCHIVE_CHATS  default FALSE — your conversations with the LLM can reveal
//                                  what you're researching / confused about.
//                                  Fail-safe OFF so a misconfigured PUBLIC
//                                  repo never leaks chats. If your instance
//                                  repo is PRIVATE (the recommended setup),
//                                  set ARCHIVE_CHATS=true to get a git backup.
function archiveStarsEnabled(): boolean {
  return process.env.ARCHIVE_STARS !== "false";
}
function archiveChatsEnabled(): boolean {
  return process.env.ARCHIVE_CHATS === "true";
}

type StarsMap = Record<string, { topic?: string; note?: string; starred_at: string }>;
type ChatMessage = { role: "user" | "assistant"; content: string; ts: string };

export async function GET(req: NextRequest) {
  if (!authorised(req)) {
    return NextResponse.json({ error: "unauthorised" }, { status: 401 });
  }

  const today = new Date().toISOString().slice(0, 10);
  const commitMsg = `data: daily archive ${today} [skip ci]`;

  const results: { path: string; changed: boolean }[] = [];
  const errors: { path: string; error: string }[] = [];
  const skipped: string[] = [];

  // 1. Stars — single shared file ----------------------------------------
  if (archiveStarsEnabled()) {
    try {
      const stars = (await kvGet<StarsMap>("stars")) ?? {};
      const snapshot = { updated_at: new Date().toISOString(), stars };
      const text = JSON.stringify(snapshot, null, 2) + "\n";
      const changed = await writeIfChanged("data/stars.json", text, commitMsg);
      results.push({ path: "data/stars.json", changed });
    } catch (err: any) {
      errors.push({
        path: "data/stars.json",
        error: err?.message ?? String(err),
      });
    }
  } else {
    skipped.push("stars (ARCHIVE_STARS=false)");
  }

  // 2. Chats — one file per paper ----------------------------------------
  if (archiveChatsEnabled()) {
    try {
      const chatKeys = await kvListKeys("chat:*");
      for (const key of chatKeys) {
        const arxivId = key.slice("chat:".length);
        try {
          const messages = (await kvGet<ChatMessage[]>(key)) ?? [];
          if (messages.length === 0) continue;
          const snapshot = {
            arxiv_id: arxivId,
            updated_at: new Date().toISOString(),
            messages,
          };
          const text = JSON.stringify(snapshot, null, 2) + "\n";
          const changed = await writeIfChanged(
            `data/chats/${arxivId}.json`,
            text,
            commitMsg,
          );
          results.push({ path: `data/chats/${arxivId}.json`, changed });
        } catch (err: any) {
          errors.push({
            path: `data/chats/${arxivId}.json`,
            error: err?.message ?? String(err),
          });
        }
      }
    } catch (err: any) {
      errors.push({ path: "chat:*", error: err?.message ?? String(err) });
    }
  } else {
    skipped.push("chats (ARCHIVE_CHATS not 'true' — chats stay KV-only)");
  }

  const commits = results.filter((r) => r.changed).length;
  return NextResponse.json({
    ok: errors.length === 0,
    date: today,
    files_checked: results.length,
    files_committed: commits,
    skipped,
    errors,
    details: results,
  });
}
