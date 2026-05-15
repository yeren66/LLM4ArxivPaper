/**
 * Write-side wrapper around the GitHub Contents API.
 *
 * The Vercel app uses this to commit periodic snapshots of KV state
 * (stars + chats) into the repo's ``data/`` directory. Writes are atomic
 * per file (GitHub uses the file's blob SHA as an optimistic lock).
 *
 * Required env (production):
 *    GH_DISPATCH_TOKEN   — fine-grained PAT with `Contents: Read and Write`
 *    GH_REPO_OWNER       — repo owner login (or fall back to VERCEL_GIT_REPO_OWNER)
 *    GH_REPO_NAME        — repo name      (or fall back to VERCEL_GIT_REPO_SLUG)
 */

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} not configured`);
  return v;
}

function repoCoords(): { owner: string; repo: string; ref: string } {
  const owner =
    process.env.GH_REPO_OWNER || process.env.VERCEL_GIT_REPO_OWNER || "";
  const repo =
    process.env.GH_REPO_NAME || process.env.VERCEL_GIT_REPO_SLUG || "";
  if (!owner || !repo) throw new Error("GH_REPO_OWNER / GH_REPO_NAME not set");
  return { owner, repo, ref: process.env.GH_DEFAULT_BRANCH || "main" };
}

type ContentsResponse = {
  sha: string;
  content: string; // base64
  encoding: "base64";
};

/** Fetch the current contents (and SHA) of a file, or null if missing. */
export async function getFile(
  pathInRepo: string,
): Promise<{ sha: string; text: string } | null> {
  const { owner, repo, ref } = repoCoords();
  const token = requireEnv("GH_DISPATCH_TOKEN");
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(
    pathInRepo,
  )}?ref=${encodeURIComponent(ref)}`;
  const res = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`getFile ${pathInRepo}: HTTP ${res.status} ${detail.slice(0, 200)}`);
  }
  const data = (await res.json()) as ContentsResponse;
  const text = Buffer.from(data.content, "base64").toString("utf-8");
  return { sha: data.sha, text };
}

/**
 * Create or update a single file. Returns the commit SHA. ``If-Match``-style
 * concurrency is handled by passing the prior `sha`; when omitted GitHub
 * creates a new file (or fails if the file already exists, which we treat
 * as "fetch + retry" for the caller).
 */
export async function putFile(
  pathInRepo: string,
  newText: string,
  commitMessage: string,
  priorSha: string | null,
): Promise<string> {
  const { owner, repo, ref } = repoCoords();
  const token = requireEnv("GH_DISPATCH_TOKEN");
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(
    pathInRepo,
  )}`;
  const body: Record<string, string> = {
    message: commitMessage,
    content: Buffer.from(newText, "utf-8").toString("base64"),
    branch: ref,
  };
  if (priorSha) body.sha = priorSha;

  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`putFile ${pathInRepo}: HTTP ${res.status} ${detail.slice(0, 200)}`);
  }
  const json = (await res.json()) as { commit: { sha: string } };
  return json.commit.sha;
}

/** Idempotent "write if changed". Returns `true` if a commit was made. */
export async function writeIfChanged(
  pathInRepo: string,
  newText: string,
  commitMessage: string,
): Promise<boolean> {
  const current = await getFile(pathInRepo);
  if (current && current.text === newText) return false;
  await putFile(pathInRepo, newText, commitMessage, current?.sha ?? null);
  return true;
}
