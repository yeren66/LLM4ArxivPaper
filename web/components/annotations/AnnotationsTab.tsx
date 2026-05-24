"use client";

/**
 * Left-rail "Notes" tab. Lists every annotation on the current paper,
 * grouped (visually, via stage badges) by which section the quote came
 * from. Clicking a card asks the article side to scroll the matching
 * highlight into view.
 */

import { useState } from "react";
import { Trash2, Pencil, Check, X, StickyNote } from "lucide-react";
import type { Annotation, AnnotationStage } from "@/lib/annotations";
import { useAnnotations } from "./AnnotationsProvider";
import { useT } from "../I18nProvider";

const STAGE_LABEL_KEY: Record<AnnotationStage, string> = {
  relevance: "section.relevance",
  brief: "section.brief",
  problem: "core.problem",
  solution: "core.solution",
  methodology: "core.methodology",
  experiments: "core.experiments",
  conclusion: "core.conclusion",
  qa: "section.qa",
};

export default function AnnotationsTab() {
  const t = useT();
  const { annotations, loading, error, remove, requestScroll } = useAnnotations();

  if (loading && annotations.length === 0) {
    return <div className="notes-empty">{t("notes.loading")}</div>;
  }
  if (error) {
    return (
      <div className="notice error" style={{ margin: "0.75rem" }}>
        {t("notes.errorPrefix")}
        {error}
      </div>
    );
  }
  if (annotations.length === 0) {
    return (
      <div className="notes-empty">
        <StickyNote size={24} />
        <div>{t("notes.empty")}</div>
      </div>
    );
  }
  return (
    <ul className="notes-list">
      {annotations.map((a) => (
        <NoteCard
          key={a.id}
          a={a}
          stageLabel={t(STAGE_LABEL_KEY[a.stage] as any)}
          onScrollTo={() => requestScroll(a.id)}
          onDelete={() => {
            if (confirm(t("notes.confirmDelete"))) remove(a.id);
          }}
        />
      ))}
    </ul>
  );
}

function NoteCard({
  a,
  stageLabel,
  onScrollTo,
  onDelete,
}: {
  a: Annotation;
  stageLabel: string;
  onScrollTo: () => void;
  onDelete: () => void;
}) {
  const t = useT();
  const { update } = useAnnotations();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(a.note);

  return (
    <li className="note-card">
      <button
        type="button"
        className="note-quote"
        onClick={onScrollTo}
        title={t("notes.scrollTo")}
      >
        <span className="note-stage-chip">{stageLabel}</span>
        <span className="note-quote-text">
          “{a.quote.length > 120 ? a.quote.slice(0, 120) + "…" : a.quote}”
        </span>
      </button>
      {!editing ? (
        <>
          {a.note ? (
            <div className="note-body">{a.note}</div>
          ) : (
            <div className="note-body note-body-empty">{t("notes.noNote")}</div>
          )}
          <div className="note-actions">
            <button
              type="button"
              className="icon-btn"
              onClick={() => {
                setDraft(a.note);
                setEditing(true);
              }}
              title={t("notes.edit")}
            >
              <Pencil size={12} />
            </button>
            <button
              type="button"
              className="icon-btn"
              onClick={onDelete}
              title={t("notes.delete")}
            >
              <Trash2 size={12} />
            </button>
          </div>
        </>
      ) : (
        <>
          <textarea
            autoFocus
            value={draft}
            rows={3}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t("notes.placeholder")}
          />
          <div className="note-actions">
            <button
              type="button"
              className="icon-btn"
              onClick={() => setEditing(false)}
              title={t("notes.cancel")}
            >
              <X size={12} />
            </button>
            <button
              type="button"
              className="icon-btn primary"
              onClick={async () => {
                await update(a.id, { note: draft });
                setEditing(false);
              }}
              title={t("notes.save")}
            >
              <Check size={12} />
            </button>
          </div>
        </>
      )}
    </li>
  );
}
