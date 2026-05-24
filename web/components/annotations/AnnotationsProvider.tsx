"use client";

/**
 * Shared annotation state for one paper. Holds the in-memory list, plus
 * helpers to add / update / delete via /api/annotations, and a "scroll to"
 * channel so the Notes tab on the left can ask the article on the right to
 * scroll a specific highlight into view.
 *
 * SelectableSection (in the article) and AnnotationsTab (in the left rail)
 * both consume this context — that's why it has to wrap the whole paper
 * shell, not just one column.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { Annotation, AnnotationStage } from "@/lib/annotations";

type ScrollListener = (id: string) => void;

type AnnotationsState = {
  arxivId: string;
  annotations: Annotation[];
  loading: boolean;
  error: string | null;
  add: (input: {
    stage: AnnotationStage;
    quote: string;
    note: string;
  }) => Promise<Annotation | null>;
  update: (id: string, patch: { note: string }) => Promise<Annotation | null>;
  remove: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
  /** Ask listeners (the article) to scroll a given annotation into view. */
  requestScroll: (id: string) => void;
  /** Article side registers a listener so it can answer requestScroll. */
  subscribeScroll: (fn: ScrollListener) => () => void;
};

const Ctx = createContext<AnnotationsState | null>(null);

export function useAnnotations(): AnnotationsState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAnnotations: AnnotationsProvider not mounted");
  return ctx;
}

export function AnnotationsProvider({
  arxivId,
  children,
}: {
  arxivId: string;
  children: React.ReactNode;
}) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollListenersRef = useRef<Set<ScrollListener>>(new Set());

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(
        `/api/annotations?arxiv_id=${encodeURIComponent(arxivId)}`,
        { cache: "no-store" },
      );
      const data = await r.json();
      if (!r.ok) {
        setError(data?.error || `HTTP ${r.status}`);
      } else {
        setAnnotations(data.annotations ?? []);
        setError(null);
      }
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, [arxivId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const add = useCallback<AnnotationsState["add"]>(
    async ({ stage, quote, note }) => {
      try {
        const r = await fetch("/api/annotations", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ arxiv_id: arxivId, stage, quote, note }),
        });
        const data = await r.json();
        if (!r.ok || !data.annotation) {
          setError(data?.error || `HTTP ${r.status}`);
          return null;
        }
        setAnnotations((prev) => [data.annotation as Annotation, ...prev]);
        return data.annotation as Annotation;
      } catch (e: any) {
        setError(e?.message ?? String(e));
        return null;
      }
    },
    [arxivId],
  );

  const update = useCallback<AnnotationsState["update"]>(
    async (id, patch) => {
      const existing = annotations.find((a) => a.id === id);
      if (!existing) return null;
      try {
        const r = await fetch("/api/annotations", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            arxiv_id: arxivId,
            id,
            stage: existing.stage,
            quote: existing.quote,
            note: patch.note,
          }),
        });
        const data = await r.json();
        if (!r.ok || !data.annotation) return null;
        setAnnotations((prev) =>
          prev.map((a) => (a.id === id ? (data.annotation as Annotation) : a)),
        );
        return data.annotation as Annotation;
      } catch {
        return null;
      }
    },
    [annotations, arxivId],
  );

  const remove = useCallback<AnnotationsState["remove"]>(
    async (id) => {
      try {
        await fetch(
          `/api/annotations?arxiv_id=${encodeURIComponent(arxivId)}&id=${encodeURIComponent(id)}`,
          { method: "DELETE" },
        );
        setAnnotations((prev) => prev.filter((a) => a.id !== id));
      } catch {
        /* swallow — UI state will resync on next refresh */
      }
    },
    [arxivId],
  );

  const subscribeScroll = useCallback<AnnotationsState["subscribeScroll"]>(
    (fn) => {
      scrollListenersRef.current.add(fn);
      return () => {
        scrollListenersRef.current.delete(fn);
      };
    },
    [],
  );

  const requestScroll = useCallback<AnnotationsState["requestScroll"]>((id) => {
    for (const fn of scrollListenersRef.current) fn(id);
  }, []);

  return (
    <Ctx.Provider
      value={{
        arxivId,
        annotations,
        loading,
        error,
        add,
        update,
        remove,
        refresh,
        requestScroll,
        subscribeScroll,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
