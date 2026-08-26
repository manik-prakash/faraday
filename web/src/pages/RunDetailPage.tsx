import { useCallback, useEffect, useState } from "react";
import { api, type RunDetail } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { TrajectoryViewer } from "../components/TrajectoryViewer";

export function RunDetailPage({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [logs, setLogs] = useState<string | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const active = ["queued", "running"];
    const tick = async (): Promise<boolean> => {
      try {
        const d = await api.run(runId);
        if (alive) {
          setRun(d);
          setError(null);
        }
        return !active.includes(d.status);
      } catch (e) {
        if (alive) setError(String(e));
        return true;
      }
    };
    (async () => {
      while (alive) {
        const done = await tick();
        if (done || !alive) break;
        await new Promise<void>((resolve) => {
          timer = window.setTimeout(resolve, 2500);
        });
      }
    })();
    return () => {
      alive = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [runId]);

  const loadLogs = useCallback(async () => {
    try {
      setLogs(await api.logs(runId));
      setLogError(null);
    } catch (e) {
      setLogError(String(e));
    }
  }, [runId]);

  if (error)
    return <p className="py-10 text-center text-red-400">failed to load run: {error}</p>;
  if (!run) return <p className="py-10 text-center text-zinc-500">loading…</p>;

  const meta = run.meta as {
    images?: { task?: string; agent?: string };
    grader?: Record<string, unknown>;
    limits?: Record<string, unknown>;
    exit_code?: number;
  };

  return (
    <div className="space-y-8">
      <button
        onClick={() => (location.hash = "#/")}
        className="text-sm text-zinc-500 hover:text-zinc-300"
      >
        ← leaderboard
      </button>

      <section className="rounded-xl p-5 ring-1 ring-zinc-800">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <h1 className="font-mono text-lg font-semibold text-zinc-100">
            {run.run_id}
          </h1>
          <StatusBadge status={run.status} />
          <Stat label="score" value={run.score.toFixed(2)} />
          <Stat
            label="duration"
            value={run.duration_s != null ? `${run.duration_s.toFixed(2)}s` : "—"}
          />
          <Stat label="exit code" value={String(meta.exit_code ?? "—")} />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <Field label="task" value={run.task_slug} />
          <Field label="agent" value={run.agent_slug} />
          <Field
            label="images"
            value={
              meta.images
                ? `${meta.images.agent ?? "?"} → ${meta.images.task ?? "?"}`
                : "—"
            }
          />
          <Field
            label="grader"
            value={meta.grader ? String(meta.grader.type ?? "—") : "—"}
          />
        </div>
        <p className="mt-4 rounded-md bg-zinc-900 px-3.5 py-2.5 font-mono text-xs text-zinc-400 ring-1 ring-zinc-800">
          {run.error ?? run.detail}
        </p>
        {run.artifacts.output_files.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs text-zinc-500">output files:</span>
            {run.artifacts.output_files.map((f) => (
              <span
                key={f}
                className="rounded bg-zinc-800/80 px-2 py-0.5 font-mono text-xs text-zinc-300"
              >
                {f}
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold tracking-tight">Trajectory</h2>
        <TrajectoryViewer steps={run.trajectory} />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Agent log</h2>
          <button
            onClick={loadLogs}
            disabled={!run.artifacts.has_logs}
            className="rounded-md bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 ring-1 ring-zinc-700 hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            load logs
          </button>
        </div>
        {logError && (
          <p className="text-sm text-red-400">could not load logs: {logError}</p>
        )}
        {logs && (
          <pre className="max-h-96 overflow-auto rounded-lg bg-black/60 p-4 font-mono text-xs leading-relaxed text-zinc-400 ring-1 ring-zinc-800">
            {logs}
          </pre>
        )}
        {!logs && !logError && (
          <p className="text-sm text-zinc-600 italic">
            {run.artifacts.has_logs
              ? "stdout/stderr captured during the run"
              : "no log file for this run"}
          </p>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs uppercase tracking-wide text-zinc-500">{label} </span>
      <span className="font-mono font-semibold text-zinc-100">{value}</span>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 rounded-md bg-zinc-900/60 px-3 py-2 ring-1 ring-zinc-800/60">
      <span className="shrink-0 text-xs text-zinc-500 pt-0.5">{label}</span>
      <span className="break-all font-mono text-xs text-zinc-300">{value}</span>
    </div>
  );
}
