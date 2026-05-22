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
import {
  readIndex,
  getDateRange,
  pickLang,
  type IndexEntry,
} from "@/lib/data-reader";
import { kvGet } from "@/lib/kv";
import { getLocale } from "@/lib/locale-server";
import { t } from "@/lib/i18n";
import HideButton from "@/components/HideButton";

// Re-read once a minute. Vercel auto-redeploys after each git push, so new
// analyses come in via redeploy; ISR is a safety net on top of that.
export const revalidate = 60;

type StarsMap = Record<string, { topic?: string; note?: string; starred_at: string }>;
type HiddenMap = Record<string, { hidden_at: string }>;

type Props = { searchParams?: { filter?: string; topic?: string } };

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
  const topicFilter = searchParams?.topic || "";
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
  // `rowsBeforeTopic` is what the active tab would show; the topic chip then
  // narrows it further so the chip counts reflect "if I click this, how many
  // would I get in this tab".
  const rowsBeforeTopic: IndexEntry[] = hiddenOnly
    ? papers.filter((p) => hiddenIds.has(p.arxiv_id))
    : starredOnly
      ? visible.filter((p) => starredIds.has(p.arxiv_id))
      : weeklyOnly
        ? weeklyPapers
        : visible;

  const topicOptions = (() => {
    const counts = new Map<string, { label: string; count: number }>();
    for (const p of rowsBeforeTopic) {
      const key = p.topic || "";
      if (!key) continue;
      const entry = counts.get(key);
      if (entry) {
        entry.count += 1;
      } else {
        counts.set(key, { label: p.topic_label || p.topic, count: 1 });
      }
    }
    return [...counts.entries()]
      .map(([name, v]) => ({ name, label: v.label, count: v.count }))
      .sort((a, b) => a.label.localeCompare(b.label));
  })();

  const rows: IndexEntry[] = topicFilter
    ? rowsBeforeTopic.filter((p) => p.topic === topicFilter)
    : rowsBeforeTopic;

  const baseFilterIds = hiddenOnly
    ? hiddenIds
    : starredOnly
      ? new Set([...starredIds].filter((id) => !hiddenIds.has(id)))
      : weeklyOnly
        ? weeklyIds
        : new Set(visible.map((p) => p.arxiv_id));

  const rangeFilterIds = topicFilter
    ? new Set(rows.map((p) => p.arxiv_id))
    : baseFilterIds;

  const range = await getDateRange({
    filterIds: rangeFilterIds,
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
          href={buildHref(null, topicFilter)}
          role="tab"
          aria-selected={!starredOnly && !weeklyOnly && !hiddenOnly}
          className={`tab ${!starredOnly && !weeklyOnly && !hiddenOnly ? "active" : ""}`}
        >
          <Newspaper /> {t(locale, "home.tab.all")}
          {visible.length > 0 && <span className="tab-count">{visible.length}</span>}
        </a>
        <a
          href={buildHref("weekly", topicFilter)}
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
          href={buildHref("starred", topicFilter)}
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
          href={buildHref("hidden", topicFilter)}
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

      {topicOptions.length > 1 && (
        <div className="topic-chips" role="tablist" aria-label="Topic filter">
          <a
            href={buildHref(filter ?? null, "")}
            role="tab"
            aria-selected={!topicFilter}
            className={`topic-chip ${!topicFilter ? "active" : ""}`}
          >
            <Tag size={11} /> {t(locale, "home.topic.all")}
            <span className="topic-chip-count">{rowsBeforeTopic.length}</span>
          </a>
          {topicOptions.map((opt) => (
            <a
              key={opt.name}
              href={buildHref(filter ?? null, opt.name)}
              role="tab"
              aria-selected={topicFilter === opt.name}
              className={`topic-chip ${topicFilter === opt.name ? "active" : ""}`}
            >
              <Tag size={11} /> {opt.label}
              <span className="topic-chip-count">{opt.count}</span>
            </a>
          ))}
        </div>
      )}

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
            {topicFilter ? (
              t(locale, "home.empty.topic")
            ) : hiddenOnly ? (
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
              title={pickLang(r.title, locale)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function buildHref(filter: string | null, topic: string): string {
  const qs = new URLSearchParams();
  if (filter) qs.set("filter", filter);
  if (topic) qs.set("topic", topic);
  const s = qs.toString();
  return s ? `/?${s}` : "/";
}

function PaperCard({
  row,
  starred,
  hidden,
  etc,
  title,
}: {
  row: IndexEntry;
  starred: boolean;
  hidden: boolean;
  etc: string;
  title: string;
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
        {title}
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
