"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

interface MatchEntry {
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function statusBadge(status: string) {
  switch (status) {
    case "completed":
      return "bg-zinc-800 text-zinc-300";
    case "in_progress":
      return "bg-green-900/50 text-green-400";
    case "scheduled":
      return "bg-blue-900/50 text-blue-400";
    case "forfeit":
      return "bg-red-900/50 text-red-400";
    default:
      return "bg-zinc-800 text-zinc-500";
  }
}

export default function AIMatchHistoryPage() {
  const params = useParams();
  const aiId = params.id as string;
  const [matches, setMatches] = useState<MatchEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/ai-profiles/${aiId}/matches?limit=50`,
          { signal: AbortSignal.timeout(10000) }
        );
        if (res.ok) {
          const data = await res.json();
          setMatches(data.matches ?? []);
        }
      } catch {
        // API might not be up
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [aiId]);

  return (
    <div className="flex flex-col gap-6 pt-8">
      <div className="flex items-center gap-3">
        <Link
          href="/my-ais"
          className="text-sm text-zinc-500 transition-colors hover:text-white"
        >
          My AIs
        </Link>
        <span className="text-zinc-700">/</span>
        <h1 className="text-xl font-bold">Match History</h1>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-14 animate-pulse rounded border border-zinc-800 bg-zinc-900/50"
            />
          ))}
        </div>
      ) : matches.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 p-8 text-center">
          <p className="text-zinc-400">No matches found for this AI.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="px-4 py-3 text-left font-medium text-zinc-400">
                  White
                </th>
                <th className="px-4 py-3 text-center font-medium text-zinc-400">
                  vs
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-400">
                  Black
                </th>
                <th className="px-4 py-3 text-center font-medium text-zinc-400">
                  Result
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  Date
                </th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m) => {
                const isWhite = m.white_ai_id === aiId;
                const won = m.winner_ai_id === aiId;
                const drew = m.status === "completed" && !m.winner_ai_id;
                const lost =
                  m.winner_ai_id !== null && m.winner_ai_id !== aiId;

                let resultText = m.status;
                let resultColor = "text-zinc-500";
                if (won) {
                  resultText = "Won";
                  resultColor = "text-green-400";
                } else if (drew) {
                  resultText = "Draw";
                  resultColor = "text-zinc-400";
                } else if (lost) {
                  resultText = "Lost";
                  resultColor = "text-red-400";
                }

                return (
                  <tr
                    key={m.id}
                    className="border-b border-zinc-800/50 transition-colors hover:bg-zinc-900/30"
                  >
                    <td
                      className={`px-4 py-3 ${isWhite ? "font-medium text-white" : "text-zinc-400"}`}
                    >
                      {m.white_name}
                    </td>
                    <td className="px-4 py-3 text-center text-zinc-600">vs</td>
                    <td
                      className={`px-4 py-3 ${!isWhite ? "font-medium text-white" : "text-zinc-400"}`}
                    >
                      {m.black_name}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {m.status === "completed" || m.status === "forfeit" ? (
                        <span className={`font-medium ${resultColor}`}>
                          {resultText}
                        </span>
                      ) : (
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${statusBadge(m.status)}`}
                        >
                          {m.status}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-500">
                      <Link
                        href={`/matches/${m.id}`}
                        className="transition-colors hover:text-white"
                      >
                        {new Date(m.created_at).toLocaleDateString()}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
