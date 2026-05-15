"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { useT } from "@/components/I18nProvider";

export default function StarButtonClient({
  arxivId,
  initial,
  topic,
}: {
  arxivId: string;
  initial: boolean;
  topic?: string | null;
}) {
  const t = useT();
  const [starred, setStarred] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (busy) return;
    const next = !starred;
    setStarred(next); // optimistic
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/stars${next ? "" : `?arxiv_id=${encodeURIComponent(arxivId)}`}`,
        {
          method: next ? "POST" : "DELETE",
          headers: next ? { "content-type": "application/json" } : undefined,
          body: next
            ? JSON.stringify({ arxiv_id: arxivId, topic: topic ?? undefined })
            : undefined,
        },
      );
      if (!res.ok) {
        setStarred(!next); // revert
        if (res.status === 401) {
          setError("__NEED_LOGIN__");
        } else {
          const body = await res.json().catch(() => ({}));
          setError(body?.error ?? `HTTP ${res.status}`);
        }
      }
    } catch (err: any) {
      setStarred(!next);
      setError(err.message ?? String(err));
    } finally {
      setBusy(false);
    }
  }

  const starLabel = starred ? t("star.starred") : t("star.star");

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        className="action-btn"
        data-pressed={starred}
        aria-pressed={starred}
        aria-label={starLabel}
        title={starLabel}
      >
        <Star
          size={14}
          fill={starred ? "#facc15" : "none"}
          color={starred ? "#ca8a04" : "currentColor"}
        />
        {starLabel}
      </button>
      {error && (
        <span style={{ color: "var(--color-error-fg)", fontSize: "0.78rem" }}>
          {error === "__NEED_LOGIN__" ? (
            <>
              {t("star.needLogin")} ·{" "}
              <a href={`/login?redirect=/papers/${arxivId}`}>{t("star.goLogin")}</a>
            </>
          ) : (
            error
          )}
        </span>
      )}
    </span>
  );
}
