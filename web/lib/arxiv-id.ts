/**
 * Tolerant arXiv URL / ID extraction.
 *
 * Accepts:
 *   2401.12345         (raw modern id)
 *   2401.12345v2       (with version)
 *   arXiv:2401.12345   (with prefix)
 *   https://arxiv.org/abs/2401.12345
 *   http://arxiv.org/abs/2401.12345v3
 *   https://arxiv.org/pdf/2401.12345.pdf
 *   cs.SE/9901001      (legacy id, pre-2007)
 *
 * Returns the canonical id without version suffix, or null if the input
 * doesn't match any known format.
 */
const MODERN = /(\d{4}\.\d{4,5})(v\d+)?/;
const LEGACY = /([a-z\-]+(?:\.[A-Z]{2})?\/\d{7})(v\d+)?/;

export function parseArxivId(input: string): string | null {
  const s = input.trim();
  if (!s) return null;
  const modern = s.match(MODERN);
  if (modern) return modern[1];
  const legacy = s.match(LEGACY);
  if (legacy) return legacy[1];
  return null;
}

export function arxivAbsUrl(id: string): string {
  return `https://arxiv.org/abs/${id}`;
}
