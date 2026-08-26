const STYLES: Record<string, string> = {
  passed: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  failed: "bg-red-500/15 text-red-400 ring-red-500/30",
  agent_error: "bg-amber-500/15 text-amber-400 ring-amber-500/30",
  error: "bg-red-500/15 text-red-300 ring-red-500/30",
  timeout: "bg-fuchsia-500/15 text-fuchsia-400 ring-fuchsia-500/30",
  running: "bg-sky-500/15 text-sky-400 ring-sky-500/30 animate-pulse",
  queued: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STYLES[status] ?? "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}
    >
      {status}
    </span>
  );
}
