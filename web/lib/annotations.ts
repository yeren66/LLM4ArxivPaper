/**
 * Per-paper inline annotations (highlighted quote + user note).
 *
 * Stored in KV under `annotations:<arxiv_id>` as an id-keyed map so single
 * writes don't have to rewrite the world. We follow the stars/hide pattern:
 * single user, ADMIN_TOKEN-gated writes, public reads (the middleware
 * matcher decides which verbs are protected).
 *
 * `stage` records which section of the paper the quote came from. The
 * `quote` field stores the selected text verbatim — we re-locate it on
 * render via a substring match instead of persisting DOM offsets, which
 * would break the moment the markdown is regenerated or the user switches
 * language.
 */
import { kvGet, kvSet } from "@/lib/kv";

export type AnnotationStage =
  | "relevance"
  | "brief"
  | "problem"
  | "solution"
  | "methodology"
  | "experiments"
  | "conclusion"
  | "qa";

export type Annotation = {
  id: string;
  arxiv_id: string;
  stage: AnnotationStage;
  quote: string;
  note: string;
  created_at: string;
  updated_at: string;
};

export type AnnotationMap = Record<string, Annotation>;

export const annotationsKey = (arxivId: string) => `annotations:${arxivId}`;

export async function getAnnotations(arxivId: string): Promise<AnnotationMap> {
  return (await kvGet<AnnotationMap>(annotationsKey(arxivId))) ?? {};
}

export async function saveAnnotations(
  arxivId: string,
  map: AnnotationMap,
): Promise<void> {
  await kvSet(annotationsKey(arxivId), map);
}

export const ANNOTATION_STAGES: ReadonlySet<AnnotationStage> = new Set([
  "relevance",
  "brief",
  "problem",
  "solution",
  "methodology",
  "experiments",
  "conclusion",
  "qa",
]);
