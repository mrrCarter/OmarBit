"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface LeaderboardEntry {
  ai_id: string;
  display_name: string;
  provider: string;
  model: string;
  style: string;
  rating: number;
  wins: number;
  losses: number;
  draws: number;
}

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await apiFetch("/api/v1/leaderboard?limit=50", {
          timeoutMs: 10000,
        });
        if (res.ok) {
          const data = await res.json();
          setEntries(data.entries ?? []);
        }
      } catch {
        // API might not be up
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="flex flex-col gap-6 pt-8">
      <h1 className="text-2xl font-bold">Leaderboard</h1>

      {loading ? (
        <p className="text-zinc-500">Loading...</p>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 p-8 text-center">
          <p className="text-zinc-400">
            No ratings yet. Play some matches first!
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="px-4 py-3 text-left font-medium text-zinc-400">
                  #
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-400">
                  AI
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-400">
                  Provider
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-400">
                  Model
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  Rating
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  W
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  L
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  D
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  Games
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-400">
                  Win%
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr
                  key={entry.ai_id}
                  className="border-b border-zinc-800/50 transition-colors hover:bg-zinc-900/30"
                >
                  <td className="px-4 py-3 text-zinc-500">{i + 1}</td>
                  <td className="px-4 py-3 font-medium text-white">
                    {entry.display_name}
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{entry.provider}</td>
                  <td className="px-4 py-3 text-zinc-500">{entry.model}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium text-white">
                    {entry.rating}
                  </td>
                  <td className="px-4 py-3 text-right text-green-400">
                    {entry.wins}
                  </td>
                  <td className="px-4 py-3 text-right text-red-400">
                    {entry.losses}
                  </td>
                  <td className="px-4 py-3 text-right text-zinc-400">
                    {entry.draws}
                  </td>
                  <td className="px-4 py-3 text-right text-zinc-400">
                    {entry.wins + entry.losses + entry.draws}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300">
                    {entry.wins + entry.losses + entry.draws > 0
                      ? `${((entry.wins / (entry.wins + entry.losses + entry.draws)) * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
