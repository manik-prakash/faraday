import type { TrajectoryStep } from "../api";

export function TrajectoryViewer({ steps }: { steps: TrajectoryStep[] }) {
  if (!steps.length) {
    return (
      <p className="text-sm text-zinc-500 italic py-4">
        no trajectory recorded for this run
      </p>
    );
  }
  const t0 = steps[0]?.ts ?? 0;
  return (
    <ol className="relative border-l border-zinc-800 ml-3 space-y-4 py-1">
      {steps.map((step, i) => (
        <li key={i} className="ml-6">
          <span className="absolute -left-[7px] mt-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-sky-500 ring-4 ring-sky-500/20" />
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="font-mono text-sm font-semibold text-zinc-100">
              {step.action ?? "step"}
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              +{(((step.ts ?? t0) - t0)).toFixed(2)}s
            </span>
          </div>
          {step.detail && (
            <pre className="mt-1.5 overflow-x-auto rounded-md bg-zinc-900 p-2.5 text-xs leading-relaxed text-zinc-400 ring-1 ring-zinc-800">
              {JSON.stringify(step.detail, null, 2)}
            </pre>
          )}
          {step.raw && (
            <pre className="mt-1.5 overflow-x-auto rounded-md bg-zinc-900 p-2.5 text-xs text-zinc-400 ring-1 ring-zinc-800">
              {step.raw}
            </pre>
          )}
        </li>
      ))}
    </ol>
  );
}
