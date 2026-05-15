/**
 * Tiny i18n: a flat string dictionary + a `t(locale, key)` lookup.
 *
 * We deliberately don't use next-intl — no locale-prefixed routes, no
 * middleware. The current locale lives in a cookie (`llm4arxiv_lang`); the
 * root layout reads it on the server and seeds <I18nProvider>, so both
 * Server and Client Components render in the right language with no FOUC.
 *
 * Note: this translates the UI *chrome* only. The analysis content itself
 * (summaries, findings, ...) is generated in whichever language
 * config/pipeline.yaml's `language` field specifies — that's a pipeline
 * concern, not a UI one.
 */

export type Locale = "zh" | "en";
export const DEFAULT_LOCALE: Locale = "zh";
export const LOCALE_COOKIE = "llm4arxiv_lang";

export function normaliseLocale(v: string | undefined | null): Locale {
  return v === "en" ? "en" : "zh";
}

// ---------------------------------------------------------------------------
// Dictionary. Keys are dot-namespaced by surface area.
// ---------------------------------------------------------------------------

const dict = {
  // -- nav / chrome --
  "nav.home": { zh: "首页", en: "Home" },
  "nav.submit": { zh: "提交论文", en: "Submit" },
  "lang.toggle": { zh: "EN", en: "中" },

  // -- home page --
  "home.title.all": { zh: "论文分析", en: "Paper Analyses" },
  "home.title.starred": { zh: "我收藏的", en: "Starred" },
  "home.title.weekly": { zh: "本周分析", en: "This Week" },
  "home.title.hidden": { zh: "已隐藏的论文", en: "Hidden Papers" },
  "home.tab.all": { zh: "全部", en: "All" },
  "home.tab.starred": { zh: "我收藏的", en: "Starred" },
  "home.tab.weekly": { zh: "本周", en: "This Week" },
  "home.tab.hidden": { zh: "已隐藏", en: "Hidden" },
  "home.empty.all": { zh: "还没有论文。", en: "No papers yet." },
  "home.empty.starred": { zh: "还没有收藏的论文。", en: "No starred papers yet." },
  "home.empty.weekly": {
    zh: "本周还没有新的分析。",
    en: "Nothing analysed this week yet.",
  },
  "home.empty.hidden": { zh: "没有隐藏的论文。", en: "No hidden papers." },
  "home.empty.submit": { zh: "提交一篇", en: "Submit one" },
  "home.empty.orWait": {
    zh: "，或等待下次 weekly 自动抓取。",
    en: ", or wait for the next weekly run.",
  },
  "home.error.title": { zh: "读取失败：", en: "Read failed: " },
  "home.error.hint": {
    zh: "确认 data/ 目录已生成、KV 已配置（本地 dev 用 in-memory fallback）",
    en: "Check that data/ exists and KV is configured (local dev uses an in-memory fallback).",
  },
  "common.etc": { zh: " 等", en: " et al." },

  // -- paper page: meta block --
  "paper.meta.topic": { zh: "Topic", en: "Topic" },
  "paper.meta.relevanceScore": { zh: "相关度", en: "Relevance" },
  "paper.meta.published": { zh: "发表", en: "Published" },
  "paper.meta.unknown": { zh: "未知", en: "Unknown" },
  "paper.generatedAt": { zh: "生成时间", en: "Generated at" },

  // -- paper page: section headings (shared with TOC) --
  "section.relevance": { zh: "与你工作的相关性", en: "Relevance to Your Work" },
  "section.brief": { zh: "论文速览", en: "At a Glance" },
  "section.core": { zh: "核心内容", en: "Core Analysis" },
  "section.qa": { zh: "关注的问题与解答", en: "Questions & Answers" },

  // -- paper page: the 5 core aspects --
  "core.problem": { zh: "主要解决了什么问题？", en: "What problem does it solve?" },
  "core.solution": { zh: "提出了什么解决方案？", en: "What solution is proposed?" },
  "core.methodology": { zh: "核心方法 / 步骤 / 策略", en: "Core methodology / steps" },
  "core.experiments": { zh: "实验设计", en: "Experiment design" },
  "core.conclusion": { zh: "发现与总结", en: "Findings & Summary" },
  "paper.figureFrom": { zh: "方法图（来自论文）", en: "Method figure (from the paper)" },
  "paper.confidence": { zh: "信心指数", en: "Confidence" },

  // -- left panel tabs --
  "panel.toc": { zh: "目录", en: "Contents" },
  "panel.chat": { zh: "对话", en: "Chat" },

  // -- star button --
  "star.starred": { zh: "已收藏", en: "Starred" },
  "star.star": { zh: "收藏", en: "Star" },
  "star.needLogin": { zh: "需要登录", en: "Login required" },
  "star.goLogin": { zh: "去登录", en: "Log in" },

  // -- hide / unhide button --
  "hide.action": { zh: "隐藏", en: "Hide" },
  "hide.restore": { zh: "恢复", en: "Unhide" },

  // -- chat panel --
  "chat.title": { zh: "针对本论文的对话", en: "Chat about this paper" },
  "chat.newSession": { zh: "新会话", en: "New session" },
  "chat.empty": {
    zh: "LLM 已预加载本文的核心分析。\n试试问 \"实验里 baseline 是什么？\" 或 \"方法在什么情况下会失败？\"",
    en: 'The LLM is pre-loaded with this paper\'s analysis.\nTry "what are the baselines?" or "when does the method fail?"',
  },
  "chat.placeholder": {
    zh: "提问，⌘/Ctrl + Enter 发送…",
    en: "Ask a question — ⌘/Ctrl + Enter to send…",
  },
  "chat.hint": { zh: "⌘/Ctrl + Enter", en: "⌘/Ctrl + Enter" },
  "chat.sending": { zh: "生成中…", en: "Generating…" },
  "chat.send": { zh: "发送", en: "Send" },
  "chat.roleUser": { zh: "你", en: "You" },
  "chat.roleAssistant": { zh: "LLM", en: "LLM" },
  "chat.historyError": { zh: "加载历史失败：", en: "Failed to load history: " },
  "chat.requestFailed": { zh: "请求失败：", en: "Request failed: " },
  "chat.resetConfirm": {
    zh: "清空当前会话历史（仅前端切换 session，旧消息仍保留在数据库）？",
    en: "Clear the current conversation? (only the local view resets; stored messages stay in the DB)",
  },

  // -- submit page --
  "submit.title": { zh: "提交一篇 arXiv 论文", en: "Submit an arXiv paper" },
  "submit.subtitle": {
    zh: "粘贴 arXiv 链接（https://arxiv.org/abs/...）或直接贴 arxiv id（2401.12345）。系统会通过 GitHub Actions 异步抓取并调 LLM 分析，约 1-3 分钟出报告。",
    en: "Paste an arXiv link (https://arxiv.org/abs/...) or a bare id (2401.12345). The system fetches + analyses it via GitHub Actions; a report appears in ~1-3 minutes.",
  },
  "submit.label.url": { zh: "arXiv URL 或 ID", en: "arXiv URL or ID" },
  "submit.label.topic": {
    zh: "归属 topic（可选，留空用默认）",
    en: "Topic (optional, defaults to the first configured topic)",
  },
  "submit.topicPlaceholder": { zh: "例如 Software Testing", en: "e.g. Software Testing" },
  "submit.button": { zh: "提交分析", en: "Analyse" },
  "submit.button.busy": { zh: "正在派发…", en: "Dispatching…" },
  "submit.progress": {
    zh: "已派发 GitHub Actions 任务（{id}），约 1-3 分钟出报告。",
    en: "Dispatched a GitHub Actions job ({id}); the report should be ready in ~1-3 minutes.",
  },

  // -- login page --
  "login.title": { zh: "登录", en: "Log in" },
  "login.subtitle": {
    zh: "单写权限。粘贴部署环境变量里 ADMIN_TOKEN 的值。浏览站点和已分析论文不需要登录。",
    en: "Write access. Paste the ADMIN_TOKEN value from your deployment env. Browsing does not require login.",
  },
  "login.label": { zh: "Admin Token", en: "Admin Token" },
  "login.button": { zh: "登录", en: "Log in" },
  "login.error": {
    zh: "Token 不匹配 — 请检查 Vercel 环境变量 ADMIN_TOKEN 的实际值。",
    en: "Token mismatch — check the actual ADMIN_TOKEN value in your Vercel env vars.",
  },
  "login.loading": { zh: "加载中…", en: "Loading…" },
} satisfies Record<string, { zh: string; en: string }>;

export type I18nKey = keyof typeof dict;

/** Look up a string. Falls back to zh, then the raw key. */
export function t(locale: Locale, key: I18nKey, vars?: Record<string, string | number>): string {
  const entry = dict[key];
  let s = entry ? entry[locale] ?? entry.zh : key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(`{${k}}`, String(v));
    }
  }
  return s;
}
