import { notFound } from "next/navigation";
import {
  Users,
  Calendar,
  Tag,
  ExternalLink,
  FileDown,
  Target,
  FileText,
  BookOpenText,
  MessagesSquare,
  ShieldCheck,
} from "lucide-react";

import { readAnalysis, pickLang } from "@/lib/data-reader";
import { kvGet } from "@/lib/kv";
import { getLocale } from "@/lib/locale-server";
import { t } from "@/lib/i18n";
import MarkdownContent from "@/components/MarkdownContent";
import PaperLeftPanel from "@/components/PaperLeftPanel";
import type { CoreAspect } from "@/components/PaperTOC";
import StarButtonClient from "./star-button";
import HideButton from "@/components/HideButton";

type StarsMap = Record<string, { topic?: string }>;
type HiddenMap = Record<string, { hidden_at: string }>;

export const revalidate = 60;

type Props = { params: { arxiv_id: string } };

export default async function PaperPage({ params }: Props) {
  const locale = getLocale();
  const arxivId = decodeURIComponent(params.arxiv_id);
  const p = await readAnalysis(arxivId).catch(() => null);
  if (!p) notFound();

  const [stars, hiddenMap] = await Promise.all([
    kvGet<StarsMap>("stars").catch(() => null),
    kvGet<HiddenMap>("hidden").catch(() => null),
  ]);
  const starred = Boolean(stars && stars[arxivId]);
  const hidden = Boolean(hiddenMap && hiddenMap[arxivId]);
  const generatedAt = p.generated_at || "";

  // The five core aspects, in display order. methodology carries the figure.
  const ASPECTS: { key: CoreAspect; labelKey: Parameters<typeof t>[1] }[] = [
    { key: "problem", labelKey: "core.problem" },
    { key: "solution", labelKey: "core.solution" },
    { key: "methodology", labelKey: "core.methodology" },
    { key: "experiments", labelKey: "core.experiments" },
    { key: "conclusion", labelKey: "core.conclusion" },
  ];
  const coreAspects: CoreAspect[] = p.core_summary
    ? ASPECTS.filter((a) =>
        pickLang((p.core_summary as any)[a.key], locale).trim(),
      ).map((a) => a.key)
    : [];

  const available = {
    relevance: Boolean(pickLang(p.relevance, locale)),
    brief: Boolean(pickLang(p.brief_summary, locale)),
    core: coreAspects.length > 0,
    qa: (p.findings?.length ?? 0) > 0,
  };

  return (
    <div className="paper-shell">
      <aside className="toc-aside">
        <div className="paper-meta-block" style={{ marginBottom: "1.25rem" }}>
          <dl>
            <div>
              <dt>{t(locale, "paper.meta.topic")}</dt>
              <dd>{p.topic_label || p.topic}</dd>
            </div>
            <div>
              <dt>{t(locale, "paper.meta.relevanceScore")}</dt>
              <dd>
                <span className="score-chip">
                  <ShieldCheck size={11} /> {Number(p.score).toFixed(1)}
                </span>
              </dd>
            </div>
            <div>
              <dt>{t(locale, "paper.meta.published")}</dt>
              <dd>
                {p.published
                  ? new Date(p.published).toISOString().slice(0, 10)
                  : t(locale, "paper.meta.unknown")}
              </dd>
            </div>
            <div>
              <dt>arXiv</dt>
              <dd>
                <a href={p.arxiv_url} target="_blank" rel="noreferrer">
                  {p.arxiv_id}
                </a>
              </dd>
            </div>
          </dl>
        </div>

        <PaperLeftPanel arxivId={arxivId} available={available} coreAspects={coreAspects} />
      </aside>

      <article className="paper-article">
        <header>
          <h1 className="paper-title">{p.title}</h1>
          <div className="article-meta">
            {p.authors?.length > 0 && (
              <span>
                <Users />
                {p.authors.slice(0, 6).join(", ")}
                {p.authors.length > 6 ? t(locale, "common.etc") : ""}
              </span>
            )}
            {p.published && (
              <span>
                <Calendar />
                {new Date(p.published).toISOString().slice(0, 10)}
              </span>
            )}
            {p.categories?.length > 0 && (
              <span>
                <Tag />
                {p.categories.slice(0, 3).join(" · ")}
              </span>
            )}
          </div>

          <div className="paper-actions">
            <a className="action-btn" href={p.arxiv_url} target="_blank" rel="noreferrer">
              <ExternalLink /> arXiv
            </a>
            {p.pdf_url && (
              <a className="action-btn" href={p.pdf_url} target="_blank" rel="noreferrer">
                <FileDown /> PDF
              </a>
            )}
            <StarButtonClient arxivId={arxivId} initial={starred} topic={p.topic} />
            <HideButton arxivId={arxivId} hidden={hidden} />
          </div>
        </header>

        {available.relevance && (
          <section id="relevance" className="article-section relevance-section">
            <div className="section-head">
              <Target />
              {t(locale, "section.relevance")}
            </div>
            <p className="relevance-text">{pickLang(p.relevance, locale)}</p>
          </section>
        )}

        {available.brief && (
          <section id="brief" className="article-section">
            <div className="section-head">
              <FileText />
              {t(locale, "section.brief")}
            </div>
            <MarkdownContent>{pickLang(p.brief_summary, locale)}</MarkdownContent>
          </section>
        )}

        {available.core && p.core_summary && (
          <section id="core" className="article-section">
            <div className="section-head">
              <BookOpenText />
              {t(locale, "section.core")}
            </div>
            {ASPECTS.map(({ key, labelKey }, idx) => {
              const body = pickLang((p.core_summary as any)[key], locale).trim();
              if (!body) return null;
              return (
                <div key={key} id={`core-${key}`} className="core-aspect">
                  <div className="subhead">
                    <span className="num">{idx + 1}</span>
                    {t(locale, labelKey)}
                  </div>
                  {/* The method figure is embedded right in the methodology aspect. */}
                  {key === "methodology" && p.figure && (() => {
                    const figCaption = pickLang(p.figure.caption, locale);
                    return (
                      <figure className="method-figure">
                        <a href={p.figure.url} target="_blank" rel="noreferrer">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={p.figure.url}
                            alt={figCaption || p.figure.label}
                            loading="lazy"
                          />
                        </a>
                        <figcaption>
                          <strong>{p.figure.label}</strong>
                          {figCaption && figCaption !== p.figure.label && (
                            <> — {stripLabelPrefix(figCaption, p.figure.label)}</>
                          )}
                        </figcaption>
                      </figure>
                    );
                  })()}
                  <MarkdownContent>{body}</MarkdownContent>
                </div>
              );
            })}
          </section>
        )}

        {available.qa && (
          <section id="qa" className="article-section">
            <div className="section-head">
              <MessagesSquare />
              {t(locale, "section.qa")}
            </div>
            <div className="qa-list">
              {p.findings.map((f, i) => {
                const reason = pickLang(f.reason, locale);
                return (
                  <div key={i} className="qa-item">
                    <div className="qa-question">
                      <MessagesSquare size={15} />
                      {pickLang(f.question, locale)}
                    </div>
                    {reason && <div className="qa-reason">{reason}</div>}
                    <MarkdownContent>{pickLang(f.answer, locale)}</MarkdownContent>
                    <span className="qa-confidence">
                      <ShieldCheck size={12} />
                      {t(locale, "paper.confidence")} {f.confidence.toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {generatedAt && (
          <p
            style={{
              color: "var(--color-text-dim)",
              fontSize: "0.8rem",
              marginTop: "2rem",
            }}
          >
            {t(locale, "paper.generatedAt")} {new Date(generatedAt).toLocaleString()}
          </p>
        )}
      </article>
    </div>
  );
}

/**
 * ar5iv figcaptions come through as "Figure 1: <caption>". Since we render
 * the label ("Figure 1") separately, drop the redundant prefix.
 */
function stripLabelPrefix(caption: string, label: string): string {
  const trimmed = caption.trim();
  if (trimmed.startsWith(label)) {
    return trimmed.slice(label.length).replace(/^[\s:：.-]+/, "").trim();
  }
  return trimmed;
}
