/**
 * Thin wrapper around GitHub's workflow_dispatch REST endpoint.
 *
 * We use this for two things:
 *   1. /api/papers/ingest → fires analyse-one.yml with the arxiv_id input.
 *   2. /api/cron/keepalive → fires weekly-pipeline.yml on a Vercel cron so
 *      the repo never goes 60 days without activity (which would otherwise
 *      cause GitHub to auto-disable the scheduled workflow).
 */

type DispatchParams = {
  workflowFile: string; // e.g. "analyse-one.yml"
  inputs?: Record<string, string>;
  ref?: string; // git ref to run the workflow against; defaults to default branch
};

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} env var is required`);
  return v;
}

export async function dispatchWorkflow(params: DispatchParams): Promise<void> {
  const owner = requireEnv("GH_REPO_OWNER");
  const repo = requireEnv("GH_REPO_NAME");
  const token = requireEnv("GH_DISPATCH_TOKEN");
  const ref = params.ref ?? "main";

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${params.workflowFile}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref, inputs: params.inputs ?? {} }),
  });

  // workflow_dispatch returns 204 on success; capture body for diagnostics
  // on any other status.
  if (res.status !== 204) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `workflow_dispatch ${params.workflowFile} failed: HTTP ${res.status} ${text.slice(0, 300)}`,
    );
  }
}
