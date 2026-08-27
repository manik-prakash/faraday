import { useCallback, useEffect, useRef, useState } from "react";
import { api, type EvalInfo } from "../api";

export function EvalsPanel() {
  const [evals, setEvals] = useState<EvalInfo[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setEvals((await api.evals()).evals);
    } catch {
      /* leaderboard already surfaces API-down */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.uploadEval(name.trim(), file);
      setMsg({ ok: true, text: `added "${res.name}" (${res.tasks.length} tasks)` });
      setName("");
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (err) {
      setMsg({ ok: false, text: String(err instanceof Error ? err.message : err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl p-5 ring-1 ring-zinc-800">
      <h2 className="mb-3 text-lg font-semibold tracking-tight">Evals</h2>
      <div className="mb-4 flex flex-wrap gap-2">
        {evals.length === 0 && <span className="text-sm text-zinc-500">none registered</span>}
        {evals.map((e) => (
          <span
            key={e.name}
            className="rounded-md bg-zinc-900 px-2.5 py-1 font-mono text-xs text-zinc-300 ring-1 ring-zinc-800"
          >
            {e.name} <span className="text-zinc-500">· {e.tasks}</span>
          </span>
        ))}
      </div>

      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <input
          value={name}
          onChange={(ev) => setName(ev.target.value)}
          placeholder="eval-name"
          className="w-40 rounded-md bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-200 ring-1 ring-zinc-800 focus:outline-none"
        />
        <input
          ref={fileRef}
          type="file"
          accept=".zip"
          className="text-xs text-zinc-400 file:mr-2 file:rounded file:border-0 file:bg-zinc-800 file:px-2 file:py-1 file:text-zinc-200"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-40"
        >
          {busy ? "uploading…" : "add eval (.zip of tasks/)"}
        </button>
      </form>
      {msg && (
        <p className={`mt-2 text-xs ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</p>
      )}
    </section>
  );
}
