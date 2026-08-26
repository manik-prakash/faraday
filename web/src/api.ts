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

export interface LeaderRow {
  task_slug: string;
  agent_slug: string;
  best_score: number;
  runs: number;
  passes: number;
  avg_duration_s: number | null;
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
  logs: async (id: string): Promise<string> => {
    const res = await fetch(`/api/runs/${id}/logs`);
    if (!res.ok) throw new Error("no logs available");
    return res.text();
  },
};
