"use client";

/**
 * Chat panel — renders the message list, history loader, input textarea
 * and streaming logic, but no positioning of its own. Embed it inside a
 * sidebar tab.
 *
 * There is exactly ONE shared conversation per paper (KV key
 * `chat:<arxiv_id>`), so chat history syncs across devices automatically —
 * no per-browser session ids. The first time the tab becomes visible
 * (driven by `active`) we lazy-load history from /api/chat/history.
 */

import { useEffect, useRef, useState, FormEvent } from "react";
import {
  Sparkles,
  RotateCcw,
  SendHorizontal,
  Bot,
  User as UserIcon,
} from "lucide-react";
import MarkdownContent from "./MarkdownContent";
import { useT } from "./I18nProvider";

type Msg = { role: "user" | "assistant"; content: string; pending?: boolean };

export type ChatPanelProps = {
  arxivId: string;
  /** True when the chat tab is currently visible. Drives lazy history load
   *  and the autofocus-on-input behaviour. */
  active: boolean;
};

export default function ChatPanel({ arxivId, active }: ChatPanelProps) {
  const t = useT();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Lazy-load history the first time the tab is shown.
  useEffect(() => {
    if (!active || historyLoaded) return;
    setHistoryLoaded(true);
    fetch(`/api/chat/history?arxiv_id=${encodeURIComponent(arxivId)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) setHistoryError(data.error);
        else
          setMessages(
            (data.messages || []).map((m: any) => ({
              role: m.role,
              content: m.content,
            })),
          );
      })
      .catch((err) => setHistoryError(err.message ?? String(err)));
  }, [active, historyLoaded, arxivId]);

  useEffect(() => {
    if (active) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, active]);

  useEffect(() => {
    if (active) setTimeout(() => textareaRef.current?.focus(), 150);
  }, [active]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);

    const userMsg: Msg = { role: "user", content: text };
    const pending: Msg = { role: "assistant", content: "", pending: true };
    setMessages((prev) => [...prev, userMsg, pending]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ arxiv_id: arxivId, message: text }),
      });
      if (!res.ok || !res.body) {
        const errText = await res.text();
        throw new Error(errText || `HTTP ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.pending)
            next[next.length - 1] = { role: "assistant", content: acc, pending: true };
          return next;
        });
      }
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.pending)
          next[next.length - 1] = { role: "assistant", content: acc };
        return next;
      });
    } catch (err: any) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        const msg = `> ${t("chat.requestFailed")}${err.message ?? String(err)}`;
        if (last && last.pending)
          next[next.length - 1] = { role: "assistant", content: msg };
        else next.push({ role: "assistant", content: msg });
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  async function resetSession() {
    if (!confirm(t("chat.resetConfirm"))) return;
    // Single shared conversation per paper — "new session" wipes it server-side.
    await fetch(`/api/chat/history?arxiv_id=${encodeURIComponent(arxivId)}`, {
      method: "DELETE",
    }).catch(() => {});
    setMessages([]);
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel-toolbar">
        <span className="chat-panel-title">
          <Sparkles size={13} />
          {t("chat.title")}
        </span>
        <button
          type="button"
          className="icon-btn"
          onClick={resetSession}
          title={t("chat.newSession")}
          aria-label={t("chat.newSession")}
        >
          <RotateCcw size={14} />
        </button>
      </div>

      <div className="chat-body">
        {historyError && (
          <div className="notice error" style={{ margin: 0 }}>
            {t("chat.historyError")}
            {historyError}
          </div>
        )}

        {messages.length === 0 && (
          <div className="chat-empty">
            <Sparkles size={26} />
            <div style={{ whiteSpace: "pre-line" }}>{t("chat.empty")}</div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            <div className="role-tag">
              {m.role === "user" ? <UserIcon size={11} /> : <Bot size={11} />}
              {m.role === "user" ? t("chat.roleUser") : t("chat.roleAssistant")}
            </div>
            {m.pending && !m.content ? (
              <span>
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </span>
            ) : (
              <MarkdownContent>{m.content}</MarkdownContent>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form className="chat-form" onSubmit={onSubmit}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          placeholder={t("chat.placeholder")}
          rows={3}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              (e.currentTarget.form as HTMLFormElement | null)?.requestSubmit();
            }
          }}
        />
        <div className="chat-form-actions">
          <span className="hint">{t("chat.hint")}</span>
          <button
            type="submit"
            className="send-btn"
            disabled={busy || !input.trim()}
          >
            <SendHorizontal size={14} />
            {busy ? t("chat.sending") : t("chat.send")}
          </button>
        </div>
      </form>
    </div>
  );
}
