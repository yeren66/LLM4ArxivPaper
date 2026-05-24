"use client";

/**
 * Wraps a section of paper content. Two jobs:
 *
 *   1. On text selection inside its bounds, surface a small floating button
 *      that opens an inline editor for a new annotation.
 *   2. On every render, re-apply yellow highlights over text that already
 *      has annotations attached. We re-apply rather than persist because
 *      ReactMarkdown owns the DOM and may rebuild it on locale switch /
 *      content update — our marks would be wiped otherwise.
 *
 * Highlight matching: we look for the annotation's `quote` as a literal
 * substring inside a single text node. Quotes that span multiple inline
 * elements (e.g., crossing a <strong>) won't highlight — they'll still
 * appear in the Notes tab marked as orphan so they're not lost.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Highlighter, X, Save } from "lucide-react";
import type { AnnotationStage } from "@/lib/annotations";
import { useAnnotations } from "./AnnotationsProvider";
import { useT } from "../I18nProvider";

const MARK_CLASS = "annotation-mark";
const MIN_QUOTE_LEN = 3;

export type SelectableSectionProps = {
  stage: AnnotationStage;
  children: React.ReactNode;
};

type PopupState = { quote: string; top: number; left: number } | null;
type EditorState = {
  quote: string;
  note: string;
  top: number;
  left: number;
} | null;

export default function SelectableSection({
  stage,
  children,
}: SelectableSectionProps) {
  const t = useT();
  const containerRef = useRef<HTMLDivElement>(null);
  const { annotations, add, subscribeScroll } = useAnnotations();
  const [popup, setPopup] = useState<PopupState>(null);
  const [editor, setEditor] = useState<EditorState>(null);

  const stageAnnotations = annotations.filter((a) => a.stage === stage);

  // Re-apply highlights after every render that could touch the DOM.
  // useLayoutEffect runs synchronously after React's commit, so we always
  // start from React's freshly-rendered tree.
  useLayoutEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    unwrapHighlights(root);
    for (const a of stageAnnotations) wrapFirstMatch(root, a.quote, a.id);
  });

  // Listen for "scroll to annotation X" requests from the Notes tab.
  useEffect(() => {
    return subscribeScroll((id) => {
      const root = containerRef.current;
      if (!root) return;
      const target = root.querySelector(
        `mark.${MARK_CLASS}[data-aid="${cssEscape(id)}"]`,
      );
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("annotation-mark-flash");
        setTimeout(() => target.classList.remove("annotation-mark-flash"), 1600);
      }
    });
  }, [subscribeScroll]);

  // Text selection → popup
  useEffect(() => {
    function onUp(ev: MouseEvent) {
      // Ignore clicks on our own popup/editor (let them handle their own UI).
      const t = ev.target as HTMLElement | null;
      if (t?.closest(".annotation-popup-btn") || t?.closest(".annotation-editor")) {
        return;
      }
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) {
        setPopup(null);
        return;
      }
      const text = sel.toString().trim();
      if (text.length < MIN_QUOTE_LEN) {
        setPopup(null);
        return;
      }
      const range = sel.getRangeAt(0);
      const root = containerRef.current;
      if (!root) return;
      // Selection has to be fully inside this section — otherwise let the
      // matching sibling SelectableSection handle it.
      if (!root.contains(range.commonAncestorContainer)) {
        setPopup(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      setPopup({
        quote: text,
        top: rect.top - 38,
        left: rect.left + rect.width / 2 - 56,
      });
    }
    document.addEventListener("mouseup", onUp);
    return () => document.removeEventListener("mouseup", onUp);
  }, []);

  // Close popup on scroll / Escape (popup is position:fixed and would
  // otherwise drift relative to the now-moved selection).
  useEffect(() => {
    if (!popup && !editor) return;
    function onScroll() {
      setPopup(null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setPopup(null);
        setEditor(null);
      }
    }
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [popup, editor]);

  const openEditor = useCallback(() => {
    if (!popup) return;
    const quote = popup.quote;
    // Re-anchor editor below the selection start. (popup.top is already 38px
    // above the selection; original top was rect.top, so add ~46 to land just
    // under the selection visually.)
    setEditor({ quote, note: "", top: popup.top + 46, left: popup.left - 60 });
    setPopup(null);
    window.getSelection()?.removeAllRanges();
  }, [popup]);

  const submit = useCallback(async () => {
    if (!editor) return;
    const { quote, note } = editor;
    setEditor(null);
    await add({ stage, quote, note });
  }, [editor, add, stage]);

  return (
    <div ref={containerRef} className="selectable-section" data-stage={stage}>
      {children}
      {popup && (
        <button
          type="button"
          className="annotation-popup-btn"
          style={{ top: popup.top, left: popup.left }}
          onMouseDown={(e) => e.preventDefault() /* keep selection alive */}
          onClick={openEditor}
        >
          <Highlighter size={12} />
          {t("notes.addBtn")}
        </button>
      )}
      {editor && (
        <div
          className="annotation-editor"
          style={{ top: editor.top, left: Math.max(8, editor.left) }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="annotation-editor-quote">
            “
            {editor.quote.length > 140
              ? editor.quote.slice(0, 140) + "…"
              : editor.quote}
            ”
          </div>
          <textarea
            autoFocus
            value={editor.note}
            onChange={(e) => setEditor({ ...editor, note: e.target.value })}
            placeholder={t("notes.placeholder")}
            rows={3}
          />
          <div className="annotation-editor-actions">
            <button type="button" onClick={() => setEditor(null)}>
              <X size={12} /> {t("notes.cancel")}
            </button>
            <button type="button" className="primary" onClick={submit}>
              <Save size={12} /> {t("notes.save")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Strip every <mark.annotation-mark> wrapper inside `root`, unwrapping its
 *  text content back into the parent. */
function unwrapHighlights(root: HTMLElement) {
  const marks = root.querySelectorAll(`mark.${MARK_CLASS}`);
  for (const m of Array.from(marks)) {
    const parent = m.parentNode;
    if (!parent) continue;
    while (m.firstChild) parent.insertBefore(m.firstChild, m);
    parent.removeChild(m);
    parent.normalize();
  }
}

/** Find the first text node containing `quote` and wrap that exact slice in
 *  a <mark>. Returns true if a match was found. */
function wrapFirstMatch(root: HTMLElement, quote: string, aid: string): boolean {
  if (!quote) return false;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const text = node as Text;
    if (!text.nodeValue) continue;
    const idx = text.nodeValue.indexOf(quote);
    if (idx === -1) continue;
    const middle = text.splitText(idx);
    middle.splitText(quote.length);
    const mark = document.createElement("mark");
    mark.className = MARK_CLASS;
    mark.dataset.aid = aid;
    mark.textContent = quote;
    middle.parentNode!.replaceChild(mark, middle);
    return true;
  }
  return false;
}

function cssEscape(s: string): string {
  // CSS.escape isn't typed everywhere; fall back to a conservative replace.
  if (typeof (window as any).CSS?.escape === "function") {
    return (window as any).CSS.escape(s);
  }
  return s.replace(/["\\\n\r]/g, "\\$&");
}
