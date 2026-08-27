export interface RunSummary {
  run_id: string;
  task_slug: string;
  agent_slug: string;
  status: string;
  score: number;
  passed: boolean;
  duration_s: number | null;
  detail: string;
  error: string | null;
  meta: Record<string, unknown>;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface TrajectoryStep {
  ts?: number;
  action?: string;
  detail?: Record<string, unknown>;
  raw?: string;
}

export interface RunDetail extends RunSummary {
  trajectory: TrajectoryStep[];
  artifacts: {
    run_dir: string;
    has_logs: boolean;
    has_trajectory: boolean;
    output_files: string[];
  };
}

export interface EvalInfo {
  name: string;
  tasks: number;
}

export interface LeaderRow {
  task_slug: string;
  agent_slug: string;
  best_score: number;
  runs: number;
  passes: number;
  avg_duration_s: number | null;
  avg_cost_usd: number | null;
  last_run: string | null;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  runs: () => getJson<{ runs: RunSummary[] }>("/api/runs"),
  run: (id: string) => getJson<RunDetail>(`/api/runs/${id}`),
  leaderboard: () => getJson<{ leaderboard: LeaderRow[] }>("/api/leaderboard"),
  evals: () => getJson<{ evals: EvalInfo[] }>("/api/evals"),
  uploadEval: async (
    name: string,
    file: File,
  ): Promise<{ name: string; tasks: string[] }> => {
    const res = await fetch(`/api/evals?name=${encodeURIComponent(name)}`, {
      method: "POST",
      body: file,
    });
    if (!res.ok) throw new Error((await res.text()) || res.statusText);
    return res.json() as Promise<{ name: string; tasks: string[] }>;
  },
  logs: async (id: string): Promise<string> => {
    const res = await fetch(`/api/runs/${id}/logs`);
    if (!res.ok) throw new Error("no logs available");
    return res.text();
  },
};
