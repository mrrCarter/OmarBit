"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Match {
  id: string;
  white_ai_id: string;
  black_ai_id: string;
  white_name: string;
  black_name: string;
  time_control: string;
  status: string;
  winner_ai_id: string | null;
  created_at: string;
  completed_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  in_progress: "bg-green-900/40 text-green-400",
  scheduled: "bg-blue-900/40 text-blue-400",
  completed: "bg-zinc-800 text-zinc-400",
  forfeit: "bg-red-900/40 text-red-400",
  aborted: "bg-zinc-800 text-zinc-500",
};

export default function MatchesPage() {
  const { data: session } = useSession();
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await apiFetch("/api/v1/matches?limit=50", {
          timeoutMs: 10000,
        });
        if (res.ok) {
          const data = await res.json();
          setMatches(data.matches ?? []);
        }
      } catch {
        // API might not be up yet
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col gap-6 pt-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Matches</h1>
        {session && (
          <Link
            href="/matches/new"
            className="rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-200"
          >
            New Match
          </Link>
        )}
      </div>

      {loading ? (
        <p className="text-zinc-500">Loading matches...</p>
      ) : matches.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 p-8 text-center">
          <p className="text-zinc-400">No matches yet.</p>
          {session && (
            <Link
              href="/matches/new"
              className="mt-3 inline-block text-sm text-white underline"
            >
              Start the first match
            </Link>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {matches.map((m) => (
            <Link
              key={m.id}
              href={`/matches/${m.id}`}
              className="flex items-center justify-between rounded-lg border border-zinc-800 px-5 py-4 transition-colors hover:border-zinc-600 hover:bg-zinc-900/50"
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span className="text-white">{m.white_name}</span>
                  <span className="text-zinc-500">vs</span>
                  <span className="text-white">{m.black_name}</span>
                </div>
                <span className="text-xs text-zinc-500">
                  {m.time_control} &middot;{" "}
                  {new Date(m.created_at).toLocaleString()}
                </span>
              </div>
              <div className="flex items-center gap-3">
                {m.status === "in_progress" && (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                )}
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[m.status] ?? "bg-zinc-800 text-zinc-400"}`}
                >
                  {m.status === "in_progress" ? "LIVE" : m.status.toUpperCase()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
