/**
 * POST /api/chat
 *
 * Body: { arxiv_id, message }
 *
 * Streams the assistant reply back as plain text. Persists both turns in
 * Upstash Redis under key `chat:<arxiv_id>` (a single shared conversation
 * per paper — cross-device sync is automatic since both devices read the
 * same key). The daily archive cron later snapshots this into
 * `data/chats/<arxiv_id>.json`.
 */

import { kvGet, kvSet } from "@/lib/kv";
import { readAnalysis } from "@/lib/data-reader";
import { buildChatSystemPrompt } from "@/lib/chat-context";

// Node runtime — Edge runtime's fetch can clash with local-network TUN
// proxies (Clash etc.); we kept hitting `fetch failed` against Redis there.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ENC = new TextEncoder();

type ChatMessage = { role: "user" | "assistant"; content: string; ts: string };

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} not configured`);
  return v;
}

function chatKey(arxivId: string): string {
  return `chat:${arxivId}`;
}

async function loadHistory(arxivId: string): Promise<ChatMessage[]> {
  return (await kvGet<ChatMessage[]>(chatKey(arxivId))) ?? [];
}

async function saveHistory(arxivId: string, messages: ChatMessage[]): Promise<void> {
  await kvSet(chatKey(arxivId), messages);
}

export async function POST(req: Request): Promise<Response> {
  let body: { arxiv_id?: string; message?: string };
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }
  const arxivId = (body.arxiv_id || "").trim();
  const message = (body.message || "").trim();
  if (!arxivId || !message)
    return json({ error: "arxiv_id and message are required" }, 400);

  // 1. Fetch the paper's analysis from filesystem (canonical store)
  const payload = await readAnalysis(arxivId);
  if (!payload) return json({ error: `no analysis for arxiv_id ${arxivId}` }, 404);

  // 2. Load conversation history from KV
  const history = await loadHistory(arxivId);

  // 3. Persist the user turn BEFORE streaming, so a hung connection doesn't
  // lose what the reader typed.
  const userTurn: ChatMessage = {
    role: "user",
    content: message,
    ts: new Date().toISOString(),
  };
  await saveHistory(arxivId, [...history, userTurn]);

  // 4. Build messages for the LLM
  const systemPrompt = buildChatSystemPrompt(payload);
  const messages: { role: string; content: string }[] = [
    { role: "system", content: systemPrompt },
    ...history.map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: message },
  ];

  // 5. Stream from the LLM (DeepSeek-compatible). Same env vars as the
  // Python pipeline so you only ever paste one set of keys.
  const baseUrl =
    process.env.LLM_BASE_URL ||
    process.env.DEEPSEEK_BASE_URL ||
    "https://api.deepseek.com/v1";
  const apiKey =
    process.env.LLM_API_KEY || process.env.DEEPSEEK_API_KEY;
  if (!apiKey) return json({ error: "LLM_API_KEY not configured" }, 500);
  const model =
    process.env.LLM_MODEL ||
    process.env.DEEPSEEK_MODEL ||
    "deepseek-v4-flash";

  const upstream = await fetch(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ model, messages, stream: true, temperature: 0.3 }),
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return json(
      { error: `upstream ${upstream.status}: ${detail.slice(0, 300)}` },
      502,
    );
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const reader = upstream.body!.getReader();
      const decoder = new TextDecoder();
      let buffered = "";
      let assistantFull = "";
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffered += decoder.decode(value, { stream: true });
          let idx: number;
          while ((idx = buffered.indexOf("\n\n")) !== -1) {
            const rawFrame = buffered.slice(0, idx);
            buffered = buffered.slice(idx + 2);
            for (const line of rawFrame.split("\n")) {
              if (!line.startsWith("data:")) continue;
              const data = line.slice(5).trim();
              if (data === "[DONE]") continue;
              try {
                const evt = JSON.parse(data);
                const delta = evt?.choices?.[0]?.delta?.content;
                if (typeof delta === "string" && delta.length > 0) {
                  assistantFull += delta;
                  controller.enqueue(ENC.encode(delta));
                }
              } catch {
                /* keep-alive frames */
              }
            }
          }
        }
        // 6. Persist the assistant turn after the stream completes
        if (assistantFull.length > 0) {
          const fresh = await loadHistory(arxivId);
          await saveHistory(arxivId, [
            ...fresh,
            {
              role: "assistant",
              content: assistantFull,
              ts: new Date().toISOString(),
            },
          ]);
        }
      } catch (err) {
        controller.enqueue(
          ENC.encode(`\n\n[stream error: ${(err as Error).message || String(err)}]`),
        );
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-arxiv-id": arxivId,
    },
  });
}

function json(obj: unknown, status: number): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}
