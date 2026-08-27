import { useEffect, useState } from "react";
import { api, type LeaderRow, type RunSummary } from "../api";
import { EvalsPanel } from "../components/EvalsPanel";
import { StatusBadge } from "../components/StatusBadge";

export function LeaderboardPage() {
  const [rows, setRows] = useState<LeaderRow[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [taskFilter, setTaskFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const [lb, rs] = await Promise.all([api.leaderboard(), api.runs()]);
        if (!alive) return;
        setError(null);
        setRows(lb.leaderboard);
        setRuns(rs.runs);
      } catch (e) {
        if (alive) setError(String(e));
      }
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const tasks = [...new Set(rows.map((r) => r.task_slug))].sort();
  const filtered = taskFilter ? rows.filter((r) => r.task_slug === taskFilter) : rows;
  const byTask = new Map<string, LeaderRow[]>();
  for (const r of filtered) {
    if (!byTask.has(r.task_slug)) byTask.set(r.task_slug, []);
    byTask.get(r.task_slug)!.push(r);
  }

  return (
    <div className="space-y-10">
      {error && (
        <div className="rounded-md bg-red-500/10 px-4 py-3 text-sm text-red-400 ring-1 ring-red-500/30">
          API unreachable — is the server running? ({error})
        </div>
      )}

      <EvalsPanel />

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Leaderboard</h2>
          {tasks.length > 0 && (
            <select
              value={taskFilter}
              onChange={(e) => setTaskFilter(e.target.value)}
              className="rounded-md bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-300 ring-1 ring-zinc-800 focus:outline-none"
            >
              <option value="">all tasks</option>
              {tasks.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          )}
        </div>

        {byTask.size === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-500">
            no results yet — submit a run with{" "}
            <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs">
              bench submit
            </code>
          </p>
        ) : (
          <div className="space-y-6">
            {[...byTask.entries()].map(([task, agents]) => (
              <div
                key={task}
                className="overflow-hidden rounded-xl ring-1 ring-zinc-800"
              >
                <div className="flex items-center justify-between bg-zinc-900/60 px-4 py-2.5">
                  <span className="font-mono text-sm font-semibold text-sky-400">
                    {task}
                  </span>
                  <span className="text-xs text-zinc-500">
                    best score per agent
                  </span>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                      <th className="px-4 py-2 font-medium">#</th>
                      <th className="px-4 py-2 font-medium">agent</th>
                      <th className="px-4 py-2 font-medium">best score</th>
                      <th className="px-4 py-2 font-medium">runs</th>
                      <th className="px-4 py-2 font-medium">passes</th>
                      <th className="px-4 py-2 font-medium">avg duration</th>
                      <th className="px-4 py-2 font-medium">avg cost</th>
                      <th className="px-4 py-2 font-medium">last run</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...agents]
                      .sort((a, b) => b.best_score - a.best_score)
                      .map((row, i) => (
                        <tr
                          key={`${row.task_slug}-${row.agent_slug}`}
                          className="border-b border-zinc-900 last:border-0"
                        >
                          <td className="px-4 py-2.5 text-zinc-500">{i + 1}</td>
                          <td className="px-4 py-2.5 font-mono font-medium text-zinc-100">
                            {row.agent_slug}
                          </td>
                          <td className="px-4 py-2.5">
                            <ScoreBar score={row.best_score} />
                          </td>
                          <td className="px-4 py-2.5 text-zinc-400">{row.runs}</td>
                          <td className="px-4 py-2.5 text-emerald-400">
                            {row.passes}
                          </td>
                          <td className="px-4 py-2.5 text-zinc-400">
                            {row.avg_duration_s != null
                              ? `${row.avg_duration_s.toFixed(2)}s`
                              : "—"}
                          </td>
                          <td className="px-4 py-2.5 font-mono text-xs text-zinc-400">
                            {row.avg_cost_usd != null
                              ? `$${row.avg_cost_usd.toFixed(4)}`
                              : "—"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-zinc-500">
                            {row.last_run
                              ? new Date(row.last_run).toLocaleString()
                              : "—"}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold tracking-tight">Recent runs</h2>
        <div className="overflow-hidden rounded-xl ring-1 ring-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/60 text-left text-xs text-zinc-500">
                <th className="px-4 py-2.5 font-medium">run</th>
                <th className="px-4 py-2.5 font-medium">task</th>
                <th className="px-4 py-2.5 font-medium">agent</th>
                <th className="px-4 py-2.5 font-medium">status</th>
                <th className="px-4 py-2.5 font-medium">score</th>
                <th className="px-4 py-2.5 font-medium">duration</th>
                <th className="px-4 py-2.5 font-medium">finished</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} className="border-b border-zinc-900 last:border-0 hover:bg-zinc-900/40">
                  <td className="px-4 py-2.5">
                    <a
                      href={`#/runs/${r.run_id}`}
                      className="font-mono text-xs text-sky-400 hover:text-sky-300 hover:underline"
                    >
                      {r.run_id}
                    </a>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs">{r.task_slug}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{r.agent_slug}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-2.5 font-mono">{r.score.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-zinc-400">
                    {r.duration_s != null ? `${r.duration_s.toFixed(1)}s` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-zinc-500">
                    {r.finished_at ? new Date(r.finished_at).toLocaleTimeString() : "—"}
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-zinc-500">
                    no runs queued yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-500" : "bg-zinc-700";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-zinc-800">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-zinc-300">{score.toFixed(2)}</span>
    </div>
  );
}
