"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChessBoard } from "@/components/chess-board";

interface MoveEvent {
  ply: number;
  san: string;
  fen: string;
  eval_cp: number | null;
  think_summary: string | null;
  chat_line: string | null;
  white_time?: number;
  black_time?: number;
}

interface MatchEnd {
  status: string;
  winner_ai_id: string | null;
  reason?: string;
  result?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function evalToPercent(cp: number | null): number {
  if (cp === null) return 50;
  const clamped = Math.max(-1000, Math.min(1000, cp));
  return 50 + (clamped / 1000) * 50;
}

function evalLabel(cp: number | null): string {
  if (cp === null) return "";
  const val = Math.abs(cp) / 100;
  if (val >= 100) return "M";
  return val.toFixed(1);
}

export default function MatchPage() {
  const params = useParams();
  const matchId = params.id as string;

  const [fen, setFen] = useState(
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
  );
  const [moves, setMoves] = useState<MoveEvent[]>([]);
  const [matchEnd, setMatchEnd] = useState<MatchEnd | null>(null);
  const [connected, setConnected] = useState(false);
  const [matchInfo, setMatchInfo] = useState<{
    white_name?: string;
    black_name?: string;
    status?: string;
  }>({});
  const [whiteTime, setWhiteTime] = useState(300);
  const [blackTime, setBlackTime] = useState(300);
  const [lastEval, setLastEval] = useState<number | null>(null);
  const [viewPly, setViewPly] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);

  const moveListRef = useRef<HTMLDivElement>(null);

  // Which ply is being displayed
  const displayPly = viewPly ?? (moves.length > 0 ? moves[moves.length - 1].ply : 0);
  const displayFen =
    viewPly !== null
      ? moves.find((m) => m.ply === viewPly)?.fen ?? fen
      : fen;

  // Determine whose turn it is
  const isWhiteTurn = displayFen.split(" ")[1] === "w";

  useEffect(() => {
    async function loadMatch() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/matches/${matchId}`);
        if (res.ok) {
          const data = await res.json();
          setMatchInfo({
            white_name: data.white_name ?? data.white_ai_id,
            black_name: data.black_name ?? data.black_ai_id,
            status: data.status,
          });
        }
      } catch {
        // ignore
      }
    }
    loadMatch();
  }, [matchId]);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let retryTimeout: ReturnType<typeof setTimeout>;

    function connect() {
      eventSource = new EventSource(
        `${API_BASE}/api/v1/stream/matches/${matchId}`
      );

      eventSource.onopen = () => setConnected(true);

      eventSource.addEventListener("move", (e) => {
        const data: MoveEvent = JSON.parse(e.data);
        setMoves((prev) => {
          if (prev.some((m) => m.ply === data.ply)) return prev;
          return [...prev, data];
        });
        setFen(data.fen);
        setViewPly(null); // snap to latest
        if (data.eval_cp !== null) setLastEval(data.eval_cp);
        if (data.white_time !== undefined) setWhiteTime(data.white_time);
        if (data.black_time !== undefined) setBlackTime(data.black_time);
      });

      eventSource.addEventListener("match_start", (e) => {
        const data = JSON.parse(e.data);
        setMatchInfo((prev) => ({
          ...prev,
          white_name: data.white_name ?? prev.white_name,
          black_name: data.black_name ?? prev.black_name,
          status: "in_progress",
        }));
      });

      eventSource.addEventListener("match_end", (e) => {
        const data: MatchEnd = JSON.parse(e.data);
        setMatchEnd(data);
        setMatchInfo((prev) => ({ ...prev, status: data.status }));
        eventSource?.close();
      });

      eventSource.addEventListener("error", (e) => {
        try {
          const data = JSON.parse((e as MessageEvent).data);
          if (data.message === "Match not found") {
            eventSource?.close();
            return;
          }
        } catch {
          // SSE connection error — retry
        }
        setConnected(false);
        eventSource?.close();
        retryTimeout = setTimeout(connect, 2000);
      });

      eventSource.onerror = () => {
        setConnected(false);
        eventSource?.close();
        retryTimeout = setTimeout(connect, 2000);
      };
    }

    connect();

    return () => {
      eventSource?.close();
      clearTimeout(retryTimeout);
    };
  }, [matchId]);

  useEffect(() => {
    if (moveListRef.current && viewPly === null) {
      moveListRef.current.scrollTop = moveListRef.current.scrollHeight;
    }
  }, [moves, viewPly]);

  const isLive = matchInfo.status === "in_progress" && !matchEnd;
  const isScheduled = matchInfo.status === "scheduled" && !matchEnd;
  const whitePercent = evalToPercent(lastEval);

  async function handleStart() {
    setStarting(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      if (!tokenRes.ok) return;
      const { token } = await tokenRes.json();

      const res = await fetch(`${API_BASE}/api/v1/matches/${matchId}/start`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setMatchInfo((prev) => ({ ...prev, status: "in_progress" }));
      }
    } catch {
      // ignore
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-4 py-4">
      {/* Status bar */}
      <div className="flex w-full max-w-[800px] items-center justify-between px-1">
        <div className="flex items-center gap-2">
          {isScheduled && (
            <button
              onClick={handleStart}
              disabled={starting}
              className="rounded bg-green-600 px-3 py-1 text-xs font-semibold text-white transition-colors hover:bg-green-500 disabled:opacity-50"
            >
              {starting ? "Starting..." : "Start Match"}
            </button>
          )}
          {isLive && (
            <span className="flex items-center gap-1.5 rounded bg-green-900/50 px-2 py-0.5 text-xs font-semibold text-green-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
              LIVE
            </span>
          )}
          {matchEnd && (
            <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs font-semibold text-zinc-300">
              {matchEnd.status === "completed" && matchEnd.result === "draw"
                ? "DRAW"
                : matchEnd.status === "completed"
                  ? "CHECKMATE"
                  : matchEnd.status === "forfeit"
                    ? "FORFEIT"
                    : matchEnd.status.toUpperCase()}
            </span>
          )}
          <span className="text-xs text-zinc-500">5+0 Blitz</span>
        </div>
        <span
          className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
          title={connected ? "Connected" : "Disconnected"}
        />
      </div>

      {/* Main layout: eval bar | board+clocks | side panel */}
      <div className="flex gap-4">
        {/* Vertical eval bar — Lichess style */}
        <div className="flex flex-col items-center gap-1">
          <span className="text-[10px] font-bold text-zinc-400">
            {lastEval !== null && lastEval < 0 ? evalLabel(lastEval) : ""}
          </span>
          <div
            className="relative overflow-hidden rounded-sm"
            style={{ width: 26, height: 360 }}
          >
            {/* White portion (bottom) */}
            <div
              className="absolute bottom-0 left-0 right-0 bg-zinc-100 transition-all duration-500 ease-out"
              style={{ height: `${whitePercent}%` }}
            />
            {/* Black portion (top) */}
            <div
              className="absolute left-0 right-0 top-0 bg-zinc-700 transition-all duration-500 ease-out"
              style={{ height: `${100 - whitePercent}%` }}
            />
          </div>
          <span className="text-[10px] font-bold text-zinc-400">
            {lastEval !== null && lastEval >= 0 ? evalLabel(lastEval) : ""}
          </span>
        </div>

        {/* Board + player bars */}
        <div className="flex flex-col">
          {/* Black player bar */}
          <div
            className={`flex items-center justify-between rounded-t px-3 py-1.5 ${
              !isWhiteTurn && isLive
                ? "bg-zinc-700"
                : "bg-zinc-800/60"
            }`}
            style={{ width: 360 }}
          >
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-sm bg-zinc-900" />
              <span className="text-sm font-medium text-zinc-200">
                {matchInfo.black_name ?? "Black"}
              </span>
            </div>
            <span
              className={`rounded px-2 py-0.5 font-mono text-sm font-bold ${
                !isWhiteTurn && isLive
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-400"
              }`}
            >
              {formatTime(blackTime)}
            </span>
          </div>

          {/* Board */}
          <ChessBoard position={displayFen} size={360} />

          {/* White player bar */}
          <div
            className={`flex items-center justify-between rounded-b px-3 py-1.5 ${
              isWhiteTurn && isLive
                ? "bg-zinc-700"
                : "bg-zinc-800/60"
            }`}
            style={{ width: 360 }}
          >
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-sm bg-zinc-200" />
              <span className="text-sm font-medium text-zinc-200">
                {matchInfo.white_name ?? "White"}
              </span>
            </div>
            <span
              className={`rounded px-2 py-0.5 font-mono text-sm font-bold ${
                isWhiteTurn && isLive
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-400"
              }`}
            >
              {formatTime(whiteTime)}
            </span>
          </div>
        </div>

        {/* Side panel */}
        <div className="flex w-[260px] flex-col">
          {/* Move list — Lichess 2-column style */}
          <div
            ref={moveListRef}
            className="flex-1 overflow-y-auto rounded-t border border-zinc-800 bg-zinc-900/40"
            style={{ maxHeight: 320 }}
          >
            {moves.length === 0 ? (
              <p className="p-4 text-center text-sm text-zinc-500">
                {isLive ? "Waiting for first move..." : "No moves yet"}
              </p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {Array.from(
                    { length: Math.ceil(moves.length / 2) },
                    (_, i) => {
                      const w = moves[i * 2];
                      const b = moves[i * 2 + 1];
                      return (
                        <tr
                          key={i}
                          className="border-b border-zinc-800/50"
                        >
                          <td className="w-8 px-2 py-1 text-right text-zinc-600">
                            {i + 1}
                          </td>
                          <td
                            className={`cursor-pointer px-2 py-1 font-medium transition-colors hover:bg-zinc-800 ${
                              w && displayPly === w.ply
                                ? "bg-zinc-700 text-white"
                                : "text-zinc-200"
                            }`}
                            onClick={() =>
                              w && setViewPly(w.ply === viewPly ? null : w.ply)
                            }
                          >
                            {w?.san ?? ""}
                          </td>
                          <td
                            className={`cursor-pointer px-2 py-1 font-medium transition-colors hover:bg-zinc-800 ${
                              b && displayPly === b.ply
                                ? "bg-zinc-700 text-white"
                                : "text-zinc-300"
                            }`}
                            onClick={() =>
                              b && setViewPly(b.ply === viewPly ? null : b.ply)
                            }
                          >
                            {b?.san ?? ""}
                          </td>
                        </tr>
                      );
                    }
                  )}
                </tbody>
              </table>
            )}
          </div>

          {/* Navigation buttons */}
          <div className="flex border border-t-0 border-zinc-800 bg-zinc-900/60 rounded-b">
            <button
              className="flex-1 px-2 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:opacity-30"
              disabled={moves.length === 0}
              onClick={() => setViewPly(moves[0]?.ply ?? null)}
              title="First move"
            >
              ⟨⟨
            </button>
            <button
              className="flex-1 px-2 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:opacity-30"
              disabled={displayPly <= (moves[0]?.ply ?? 0)}
              onClick={() => {
                const idx = moves.findIndex((m) => m.ply === displayPly);
                if (idx > 0) setViewPly(moves[idx - 1].ply);
              }}
              title="Previous move"
            >
              ⟨
            </button>
            <button
              className="flex-1 px-2 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:opacity-30"
              disabled={
                displayPly >= (moves[moves.length - 1]?.ply ?? 0)
              }
              onClick={() => {
                const idx = moves.findIndex((m) => m.ply === displayPly);
                if (idx < moves.length - 1) setViewPly(moves[idx + 1].ply);
              }}
              title="Next move"
            >
              ⟩
            </button>
            <button
              className="flex-1 px-2 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:opacity-30"
              disabled={viewPly === null}
              onClick={() => setViewPly(null)}
              title="Latest move"
            >
              ⟩⟩
            </button>
          </div>

          {/* AI Thoughts — live stream of both players' reasoning */}
          <div className="mt-3 flex flex-col gap-0.5 rounded border border-zinc-800 bg-zinc-900/40 p-2">
            <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              AI Thoughts
            </h3>
            <div className="max-h-[140px] space-y-1.5 overflow-y-auto">
              {moves.slice(-8).map((m) => {
                const isWhiteMove = m.ply % 2 === 1;
                const name = isWhiteMove
                  ? matchInfo.white_name ?? "White"
                  : matchInfo.black_name ?? "Black";
                return (
                  <div
                    key={m.ply}
                    className={`rounded px-2 py-1 text-xs ${
                      isWhiteMove
                        ? "border-l-2 border-zinc-400 bg-zinc-800/50"
                        : "border-l-2 border-zinc-600 bg-zinc-800/30"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <div
                        className={`h-2 w-2 rounded-sm ${
                          isWhiteMove ? "bg-zinc-200" : "bg-zinc-700"
                        }`}
                      />
                      <span className="font-medium text-zinc-300">
                        {name}
                      </span>
                      <span className="text-zinc-600">played</span>
                      <span className="font-mono font-medium text-white">
                        {m.san}
                      </span>
                    </div>
                    {m.think_summary && (
                      <p className="mt-0.5 italic text-zinc-500">
                        {m.think_summary}
                      </p>
                    )}
                    {m.chat_line && (
                      <p className="mt-0.5 text-zinc-400">
                        &ldquo;{m.chat_line}&rdquo;
                      </p>
                    )}
                  </div>
                );
              })}
              {moves.length === 0 && (
                <p className="text-xs text-zinc-600">
                  Waiting for moves...
                </p>
              )}
            </div>
          </div>

          {/* Match result */}
          {matchEnd && (
            <div className="mt-3 rounded border border-zinc-700 bg-zinc-800 p-3 text-center">
              <p className="text-sm font-semibold text-white">
                {matchEnd.status === "completed" && matchEnd.result === "draw"
                  ? "½ - ½"
                  : matchEnd.status === "completed"
                    ? matchEnd.winner_ai_id
                      ? "1 - 0"
                      : "0 - 1"
                    : "Game Over"}
              </p>
              {matchEnd.reason && (
                <p className="mt-0.5 text-xs text-zinc-400">
                  {matchEnd.reason}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
