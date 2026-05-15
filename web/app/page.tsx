import {
  Newspaper,
  Star,
  ShieldCheck,
  Tag,
  Users,
  Calendar,
  CalendarDays,
  Trash2,
  Inbox,
  Info,
} from "lucide-react";
import { readIndex, getDateRange, type IndexEntry } from "@/lib/data-reader";
import { kvGet } from "@/lib/kv";
import { getLocale } from "@/lib/locale-server";
import { t } from "@/lib/i18n";
import HideButton from "@/components/HideButton";

// Re-read once a minute. Vercel auto-redeploys after each git push, so new
// analyses come in via redeploy; ISR is a safety net on top of that.
export const revalidate = 60;

type StarsMap = Record<string, { topic?: string; note?: string; starred_at: string }>;
type HiddenMap = Record<string, { hidden_at: string }>;

type Props = { searchParams?: { filter?: string } };

// A paper counts as "this week" if its analysis was generated within the
// last 7 days — i.e. it came out of the most recent weekly run.
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
function isThisWeek(p: IndexEntry): boolean {
  if (!p.generated_at) return false;
  const ts = new Date(p.generated_at).getTime();
  return Number.isFinite(ts) && ts >= Date.now() - WEEK_MS;
}

export default async function HomePage({ searchParams }: Props) {
  const locale = getLocale();
  const filter = searchParams?.filter;
  const starredOnly = filter === "starred";
  const weeklyOnly = filter === "weekly";
  const hiddenOnly = filter === "hidden";

  // Read analyses index (filesystem), stars, and hidden (KV) in parallel.
  let papers: IndexEntry[] = [];
  let stars: StarsMap = {};
  let hidden: HiddenMap = {};
  let dataError: string | null = null;
  try {
    const [index, kvStars, kvHidden] = await Promise.all([
      readIndex(),
      kvGet<StarsMap>("stars"),
      kvGet<HiddenMap>("hidden"),
    ]);
    papers = index.papers;
    stars = kvStars ?? {};
    hidden = kvHidden ?? {};
  } catch (err: any) {
    dataError = err?.message ?? String(err);
  }

  const starredIds = new Set(Object.keys(stars));
  const hiddenIds = new Set(Object.keys(hidden));
  const visible = papers.filter((p) => !hiddenIds.has(p.arxiv_id));
  const weeklyPapers = visible.filter(isThisWeek);
  const weeklyIds = new Set(weeklyPapers.map((p) => p.arxiv_id));

  // Hidden papers surface only in the dedicated tab. The other three tabs
  // filter them out (a hidden paper that was previously starred stays hidden).
  const rows: IndexEntry[] = hiddenOnly
    ? papers.filter((p) => hiddenIds.has(p.arxiv_id))
    : starredOnly
      ? visible.filter((p) => starredIds.has(p.arxiv_id))
      : weeklyOnly
        ? weeklyPapers
        : visible;

  const range = await getDateRange({
    filterIds: hiddenOnly
      ? hiddenIds
      : starredOnly
        ? new Set([...starredIds].filter((id) => !hiddenIds.has(id)))
        : weeklyOnly
          ? weeklyIds
          : new Set(visible.map((p) => p.arxiv_id)),
  }).catch(() => ({ start: null, end: null, count: rows.length }));

  const rangeSuffix = (() => {
    if (!range.start || !range.end) return "";
    if (range.start === range.end) return `（${range.start}）`;
    return `（${range.start} — ${range.end}）`;
  })();

  return (
    <div className="container">
      <h1 className="page-title">
        {hiddenOnly ? (
          <Trash2 />
        ) : starredOnly ? (
          <Star />
        ) : weeklyOnly ? (
          <CalendarDays />
        ) : (
          <Newspaper />
        )}
        {hiddenOnly
          ? t(locale, "home.title.hidden")
          : starredOnly
            ? t(locale, "home.title.starred")
            : weeklyOnly
              ? t(locale, "home.title.weekly")
              : t(locale, "home.title.all")}
        {!starredOnly && !hiddenOnly && rangeSuffix && (
          <span className="page-title-range">{rangeSuffix}</span>
        )}
      </h1>

      <div className="tabs" role="tablist">
        <a
          href="/"
          role="tab"
          aria-selected={!starredOnly && !weeklyOnly && !hiddenOnly}
          className={`tab ${!starredOnly && !weeklyOnly && !hiddenOnly ? "active" : ""}`}
        >
          <Newspaper /> {t(locale, "home.tab.all")}
          {visible.length > 0 && <span className="tab-count">{visible.length}</span>}
        </a>
        <a
          href="/?filter=weekly"
          role="tab"
          aria-selected={weeklyOnly}
          className={`tab ${weeklyOnly ? "active" : ""}`}
        >
          <CalendarDays /> {t(locale, "home.tab.weekly")}
          {weeklyIds.size > 0 && (
            <span className="tab-count">{weeklyIds.size}</span>
          )}
        </a>
        <a
          href="/?filter=starred"
          role="tab"
          aria-selected={starredOnly}
          className={`tab ${starredOnly ? "active" : ""}`}
        >
          <Star /> {t(locale, "home.tab.starred")}
          {starredIds.size > 0 && (
            <span className="tab-count">{starredIds.size}</span>
          )}
        </a>
        <a
          href="/?filter=hidden"
          role="tab"
          aria-selected={hiddenOnly}
          className={`tab ${hiddenOnly ? "active" : ""}`}
        >
          <Trash2 /> {t(locale, "home.tab.hidden")}
          {hiddenIds.size > 0 && (
            <span className="tab-count">{hiddenIds.size}</span>
          )}
        </a>
      </div>

      {dataError && (
        <div className="notice error">
          <Info />
          <div>
            <strong>{t(locale, "home.error.title")}</strong> {dataError}
            <div style={{ marginTop: ".35rem", fontSize: ".84rem", opacity: 0.8 }}>
              {t(locale, "home.error.hint")}
            </div>
          </div>
        </div>
      )}

      {!dataError && rows.length === 0 && (
        <div className="empty-state">
          <Inbox />
          <div>
            {hiddenOnly ? (
              t(locale, "home.empty.hidden")
            ) : starredOnly ? (
              t(locale, "home.empty.starred")
            ) : weeklyOnly ? (
              t(locale, "home.empty.weekly")
            ) : (
              <>
                {t(locale, "home.empty.all")}{" "}
                <a href="/submit">{t(locale, "home.empty.submit")}</a>
                {t(locale, "home.empty.orWait")}
              </>
            )}
          </div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="paper-grid">
          {rows.map((r) => (
            <PaperCard
              key={r.arxiv_id}
              row={r}
              starred={starredIds.has(r.arxiv_id)}
              hidden={hiddenIds.has(r.arxiv_id)}
              etc={t(locale, "common.etc")}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PaperCard({
  row,
  starred,
  hidden,
  etc,
}: {
  row: IndexEntry;
  starred: boolean;
  hidden: boolean;
  etc: string;
}) {
  return (
    <article className="paper-card">
      <a href={`/papers/${row.arxiv_id}`} className="paper-card-title">
        {starred && (
          <Star
            size={14}
            fill="#facc15"
            color="#ca8a04"
            style={{ marginRight: 4, verticalAlign: -2 }}
          />
        )}
        {row.title}
      </a>
      <div className="paper-card-meta">
        <span className="score-chip">
          <ShieldCheck size={11} /> {Number(row.score).toFixed(1)}
        </span>
        <span className="topic-chip">
          <Tag size={11} /> {row.topic_label || row.topic}
        </span>
        {row.authors.length > 0 && (
          <span>
            <Users />
            {row.authors.slice(0, 3).join(", ")}
            {row.authors.length > 3 ? etc : ""}
          </span>
        )}
        {row.published && (
          <span>
            <Calendar />
            {row.published}
          </span>
        )}
        <span className="paper-card-actions">
          <HideButton arxivId={row.arxiv_id} hidden={hidden} iconOnly />
        </span>
      </div>
    </article>
  );
}
