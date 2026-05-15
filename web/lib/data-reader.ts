/**
 * Read analyses produced by the Python pipeline from the local filesystem.
 *
 * The pipeline writes:
 *     data/analyses/{arxiv_id}.json   — full payload for one paper
 *     data/index.json                 — slim list of every paper, newest first
 *
 * These files are part of the git repo and get bundled into the Vercel
 * deployment. The Next.js server can therefore read them as ordinary files
 * (no API calls, no auth, no rate limits). When the weekly pipeline pushes
 * new analyses, Vercel auto-redeploys and the new files become readable.
 *
 * Type contract: stays in sync with src/workflow/pipeline.py:_summary_to_payload.
 */

import { promises as fs } from "node:fs";
import path from "node:path";

// Project root is two parents up from web/ (which is itself one parent up
// from web/lib). Resolves correctly in both `next dev` (cwd = web/) and
// in the deployed Vercel function.
const DATA_DIR = process.env.DATA_DIR
  ? path.resolve(process.env.DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");

// ---------------------------------------------------------------------------
// Types (mirror Python's _summary_to_payload)
// ---------------------------------------------------------------------------

/**
 * A bilingual text field. The Python pipeline generates the analysis in
 * English and (when openai.language is not "en") translates it; both live
 * here. Use `pickLang` to read the right one for the current UI locale.
 */
export type BiText = { en: string; zh: string };

/**
 * Read a bilingual field for the given UI locale. Tolerates legacy
 * plain-string payloads written before the bilingual change, so old
 * analyses still render until they are re-generated.
 */
export function pickLang(
  t: BiText | string | null | undefined,
  locale: "zh" | "en",
): string {
  if (t == null) return "";
  if (typeof t === "string") return t;
  return (locale === "zh" ? t.zh : t.en) || t.en || t.zh || "";
}

export type AnalysisPayload = {
  arxiv_id: string;
  topic: string;
  topic_label: string;
  title: string;
  authors: string[];
  affiliations: string[];
  categories: string[];
  published: string | null;
  updated: string | null;
  abstract: string;
  arxiv_url: string;
  pdf_url: string | null;
  comment: string | null;
  relevance: BiText;
  figure: { label: string; caption: BiText; url: string; reference_text: string } | null;
  brief_summary: BiText;
  core_summary: {
    problem: BiText;
    solution: BiText;
    methodology: BiText;
    experiments: BiText;
    conclusion: BiText; // the 5th aspect — rendered as "Findings & Summary"
  } | null;
  tasks: { question: BiText; reason: BiText }[];
  findings: { question: BiText; reason: BiText; answer: BiText; confidence: number }[];
  score: number;
  score_dimensions: { name: string; weight: number; value: number }[];
  markdown: string;
  model?: string;
  generated_at?: string;
};

export type IndexEntry = {
  arxiv_id: string;
  topic: string;
  topic_label: string;
  title: string;
  authors: string[];
  score: number;
  published: string | null;
  generated_at: string;
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

async function readJson<T>(p: string): Promise<T | null> {
  try {
    const text = await fs.readFile(p, "utf-8");
    return JSON.parse(text) as T;
  } catch (err: any) {
    if (err?.code === "ENOENT") return null;
    throw err;
  }
}

/** Return one paper's full analysis, or null if not yet generated. */
export async function readAnalysis(arxivId: string): Promise<AnalysisPayload | null> {
  return readJson<AnalysisPayload>(
    path.join(DATA_DIR, "analyses", `${arxivId}.json`),
  );
}

/** Read the slim index (sorted newest-first by the pipeline). */
export async function readIndex(): Promise<{
  papers: IndexEntry[];
  updated_at: string | null;
}> {
  const data = await readJson<{ papers: IndexEntry[]; updated_at?: string }>(
    path.join(DATA_DIR, "index.json"),
  );
  return {
    papers: data?.papers ?? [],
    updated_at: data?.updated_at ?? null,
  };
}

/** Cheap existence check used by /api/papers/[id]/status during URL ingest. */
export async function analysisExists(arxivId: string): Promise<boolean> {
  try {
    await fs.access(path.join(DATA_DIR, "analyses", `${arxivId}.json`));
    return true;
  } catch {
    return false;
  }
}

/** Min/max published dates across the index — drives the home page title. */
export async function getDateRange(opts: {
  filterIds?: Set<string>;
} = {}): Promise<{ start: string | null; end: string | null; count: number }> {
  const { papers } = await readIndex();
  const dates = papers
    .filter((p) => !opts.filterIds || opts.filterIds.has(p.arxiv_id))
    .map((p) => p.published)
    .filter((d): d is string => Boolean(d));
  if (dates.length === 0) {
    return {
      start: null,
      end: null,
      count: opts.filterIds
        ? papers.filter((p) => opts.filterIds!.has(p.arxiv_id)).length
        : papers.length,
    };
  }
  dates.sort();
  return {
    start: dates[0],
    end: dates[dates.length - 1],
    count: opts.filterIds
      ? papers.filter((p) => opts.filterIds!.has(p.arxiv_id)).length
      : papers.length,
  };
}

/** Surface where we're reading from (for debug banners). */
export function dataDir(): string {
  return DATA_DIR;
}
