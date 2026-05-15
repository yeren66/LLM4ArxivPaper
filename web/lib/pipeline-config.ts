/**
 * Read non-secret settings out of ``config/pipeline.yaml`` so the web app
 * and the Python pipeline share one source of truth.
 *
 * The YAML lives in the git repo and is bundled into the Vercel deployment,
 * so the Node runtime can read it as an ordinary file (no API call needed).
 *
 * Env vars still win when set, so a power user can override on a per-
 * deployment basis without touching the file in git.
 */

import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

// One level deeper than data/ — the YAML lives at the repo root, so two
// parents up from web/lib/ in dev. Same env override as DATA_DIR uses.
const CONFIG_PATH = process.env.PIPELINE_CONFIG_PATH
  ? path.resolve(process.env.PIPELINE_CONFIG_PATH)
  : path.resolve(process.cwd(), "..", "config", "pipeline.yaml");

type RawConfig = {
  openai?: { summarization_model?: string; language?: string };
  archive?: { stars?: boolean; chats?: boolean };
};

export type PipelineConfig = {
  /** The LLM model name the pipeline uses for analysis — the chat route
   *  uses the same model unless LLM_MODEL overrides it in the environment. */
  summarizationModel: string;
  /** Output language of the LLM analyses; unused by the web app today, kept
   *  here in case a future feature needs it. */
  language: string;
  /** Archive policy for the daily archive-to-git cron. Env vars
   *  ARCHIVE_STARS / ARCHIVE_CHATS override these when set. */
  archiveStars: boolean;
  archiveChats: boolean;
};

let cached: PipelineConfig | null = null;

function parse(raw: string): PipelineConfig {
  const doc = (yaml.load(raw) ?? {}) as RawConfig;
  return {
    summarizationModel: doc.openai?.summarization_model || "deepseek-v4-flash",
    language: doc.openai?.language || "zh-CN",
    archiveStars: doc.archive?.stars ?? true,
    archiveChats: doc.archive?.chats ?? false,
  };
}

/** Read and cache the pipeline config. Falls back to sensible defaults if
 *  the YAML can't be read — the web app should still work in that case. */
export async function getPipelineConfig(): Promise<PipelineConfig> {
  if (cached) return cached;
  try {
    const text = await fs.readFile(CONFIG_PATH, "utf-8");
    cached = parse(text);
  } catch {
    cached = {
      summarizationModel: "deepseek-v4-flash",
      language: "zh-CN",
      archiveStars: true,
      archiveChats: false,
    };
  }
  return cached;
}

/** Env vars override the YAML when set. */
export async function resolvedLLMModel(): Promise<string> {
  const fromEnv =
    process.env.LLM_MODEL?.trim() || process.env.DEEPSEEK_MODEL?.trim();
  if (fromEnv) return fromEnv;
  const cfg = await getPipelineConfig();
  return cfg.summarizationModel;
}

export async function resolvedArchiveStars(): Promise<boolean> {
  const env = process.env.ARCHIVE_STARS?.trim().toLowerCase();
  if (env === "true") return true;
  if (env === "false") return false;
  return (await getPipelineConfig()).archiveStars;
}

export async function resolvedArchiveChats(): Promise<boolean> {
  const env = process.env.ARCHIVE_CHATS?.trim().toLowerCase();
  if (env === "true") return true;
  if (env === "false") return false;
  return (await getPipelineConfig()).archiveChats;
}
