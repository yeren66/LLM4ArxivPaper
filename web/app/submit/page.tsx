"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus, Info, AlertCircle, Loader2 } from "lucide-react";
import { useT } from "@/components/I18nProvider";

export default function SubmitPage() {
  const t = useT();
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setProgress(null);
    setBusy(true);
    try {
      const res = await fetch("/api/papers/ingest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url, topic: topic || undefined }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.error || `HTTP ${res.status}`);

      if (body.status === "already_analysed") {
        router.push(`/papers/${body.arxiv_id}`);
        return;
      }
      setProgress(t("submit.progress", { id: body.arxiv_id }));
      const arxivId = body.arxiv_id;
      const poll = async () => {
        const s = await fetch(`/api/papers/${arxivId}/status`).then((r) => r.json());
        if (s.ready) router.push(`/papers/${arxivId}`);
        else setTimeout(poll, 8000);
      };
      poll();
    } catch (err: any) {
      setError(err.message ?? String(err));
      setBusy(false);
    }
  }

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <h1 className="page-title">
        <Plus /> {t("submit.title")}
      </h1>
      <p className="page-subtitle">{t("submit.subtitle")}</p>

      <form className="form-card" onSubmit={onSubmit}>
        <label htmlFor="url">{t("submit.label.url")}</label>
        <input
          id="url"
          type="text"
          required
          placeholder="https://arxiv.org/abs/2401.12345"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={busy}
        />

        <label htmlFor="topic">{t("submit.label.topic")}</label>
        <input
          id="topic"
          type="text"
          placeholder={t("submit.topicPlaceholder")}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={busy}
        />

        <button type="submit" disabled={busy}>
          {busy ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: ".4rem" }}>
              <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
              {t("submit.button.busy")}
            </span>
          ) : (
            t("submit.button")
          )}
        </button>
      </form>

      {progress && (
        <div className="notice info">
          <Info />
          {progress}
        </div>
      )}
      {error && (
        <div className="notice error">
          <AlertCircle />
          {error}
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
