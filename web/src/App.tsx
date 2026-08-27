import { useEffect, useState } from "react";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { RunDetailPage } from "./pages/RunDetailPage";

function useHashRoute(): { page: "home" | "run"; runId?: string } {
  const parse = () => {
    const hash = location.hash.replace(/^#\/?/, "");
    const m = hash.match(/^runs\/(.+)$/);
    return m ? { page: "run" as const, runId: m[1] } : { page: "home" as const };
  };
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onChange = () => setRoute(parse());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export default function App() {
  const route = useHashRoute();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
          <a href="#/" className="flex items-baseline gap-2">
            <span className="text-lg font-bold tracking-tight text-zinc-50">
              Faraday
            </span>
            <span className="hidden text-xs text-zinc-500 sm:inline">
              bring-your-own-agent benchmarks
            </span>
          </a>
          <a
            href="#/"
            className="text-sm text-zinc-400 transition-colors hover:text-zinc-100"
          >
            leaderboard
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        {route.page === "home" ? (
          <LeaderboardPage />
        ) : (
          <RunDetailPage runId={route.runId!} />
        )}
      </main>
    </div>
  );
}
