"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Undo2 } from "lucide-react";
import { useT } from "@/components/I18nProvider";

/**
 * Hide / Unhide button. Posts to /api/hide and refreshes the page so the
 * card disappears from (or reappears in) the current filter view.
 *
 * Two visual modes:
 *   - `iconOnly` for the home-page card row (compact)
 *   - default     for the paper detail page action bar (icon + label)
 */
export default function HideButton({
  arxivId,
  hidden,
  iconOnly = false,
}: {
  arxivId: string;
  hidden: boolean;
  iconOnly?: boolean;
}) {
  const t = useT();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle(e?: React.MouseEvent) {
    e?.stopPropagation();
    e?.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        hidden ? `/api/hide?arxiv_id=${encodeURIComponent(arxivId)}` : `/api/hide`,
        {
          method: hidden ? "DELETE" : "POST",
          headers: hidden ? undefined : { "content-type": "application/json" },
          body: hidden ? undefined : JSON.stringify({ arxiv_id: arxivId }),
        },
      );
      if (!res.ok) {
        if (res.status === 401) {
          setError("__NEED_LOGIN__");
        } else {
          const body = await res.json().catch(() => ({}));
          setError(body?.error ?? `HTTP ${res.status}`);
        }
        return;
      }
      router.refresh();
    } catch (err: any) {
      setError(err.message ?? String(err));
    } finally {
      setBusy(false);
    }
  }

  const label = hidden ? t("hide.restore") : t("hide.action");
  const Icon = hidden ? Undo2 : Trash2;

  if (iconOnly) {
    return (
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        className="card-action"
        aria-label={label}
        title={label}
      >
        <Icon size={14} />
      </button>
    );
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        className="action-btn"
        aria-label={label}
        title={label}
      >
        <Icon size={14} />
        {label}
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
