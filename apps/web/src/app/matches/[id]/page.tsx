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

function evalToBar(cp: number | null): number {
  if (cp === null) return 50;
  const clamped = Math.max(-500, Math.min(500, cp));
  return 50 + (clamped / 500) * 50;
}

export default function MatchPage() {
  const params = useParams();
  const matchId = params.id as string;

  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
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

  const moveListRef = useRef<HTMLDivElement>(null);

  // Load match info
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

  // SSE connection
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

  // Auto-scroll move list
  useEffect(() => {
    if (moveListRef.current) {
      moveListRef.current.scrollTop = moveListRef.current.scrollHeight;
    }
  }, [moves]);

  const isLive = matchInfo.status === "in_progress" && !matchEnd;

  return (
    <div className="flex flex-col gap-6 pt-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">
            {matchInfo.white_name ?? "White"} vs{" "}
            {matchInfo.black_name ?? "Black"}
          </h1>
          <p className="text-sm text-zinc-500">5+0 blitz</p>
        </div>
        <div className="flex items-center gap-2">
          {isLive && (
            <span className="flex items-center gap-1.5 rounded-full bg-green-900/40 px-3 py-1 text-xs font-medium text-green-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
              LIVE
            </span>
          )}
          {matchEnd && (
            <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-400">
              {matchEnd.status.toUpperCase()}
            </span>
          )}
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
            title={connected ? "Connected" : "Disconnected"}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Board + clocks */}
        <div className="flex flex-col gap-3">
          {/* Black clock */}
          <div className="flex items-center justify-between rounded-md border border-zinc-800 px-4 py-2">
            <span className="text-sm text-zinc-400">
              {matchInfo.black_name ?? "Black"}
            </span>
            <span className="font-mono text-lg text-white">
              {formatTime(blackTime)}
            </span>
          </div>

          {/* Chess board */}
          <div className="w-[360px]">
            <ChessBoard position={fen} size={360} />
          </div>

          {/* White clock */}
          <div className="flex items-center justify-between rounded-md border border-zinc-800 px-4 py-2">
            <span className="text-sm text-zinc-400">
              {matchInfo.white_name ?? "White"}
            </span>
            <span className="font-mono text-lg text-white">
              {formatTime(whiteTime)}
            </span>
          </div>
        </div>

        {/* Side panel */}
        <div className="flex flex-1 flex-col gap-4">
          {/* Eval bar */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs text-zinc-500">
              <span>Black</span>
              <span>
                {lastEval !== null
                  ? `${lastEval > 0 ? "+" : ""}${(lastEval / 100).toFixed(1)}`
                  : "—"}
              </span>
              <span>White</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full bg-white transition-all duration-300"
                style={{ width: `${evalToBar(lastEval)}%` }}
              />
            </div>
          </div>

          {/* Move list */}
          <div
            ref={moveListRef}
            className="max-h-[320px] overflow-y-auto rounded-md border border-zinc-800 p-3"
          >
            {moves.length === 0 ? (
              <p className="text-sm text-zinc-500">
                {isLive ? "Waiting for first move..." : "No moves yet"}
              </p>
            ) : (
              <div className="grid grid-cols-[2rem_1fr_1fr] gap-y-0.5 text-sm">
                {Array.from(
                  { length: Math.ceil(moves.length / 2) },
                  (_, i) => {
                    const w = moves[i * 2];
                    const b = moves[i * 2 + 1];
                    return (
                      <div key={i} className="contents">
                        <span className="text-zinc-600">{i + 1}.</span>
                        <span className="text-white">{w?.san ?? ""}</span>
                        <span className="text-zinc-300">{b?.san ?? ""}</span>
                      </div>
                    );
                  }
                )}
              </div>
            )}
          </div>

          {/* Chat / Think summaries */}
          <div className="flex flex-col gap-2 rounded-md border border-zinc-800 p-3">
            <h3 className="text-xs font-medium uppercase text-zinc-500">
              AI Chat
            </h3>
            <div className="max-h-[150px] overflow-y-auto">
              {moves
                .filter((m) => m.chat_line || m.think_summary)
                .slice(-10)
                .map((m) => (
                  <div key={m.ply} className="text-xs">
                    {m.chat_line && (
                      <p className="text-zinc-300">
                        <span className="text-zinc-500">ply {m.ply}:</span>{" "}
                        {m.chat_line}
                      </p>
                    )}
                    {m.think_summary && (
                      <p className="italic text-zinc-500">
                        {m.think_summary}
                      </p>
                    )}
                  </div>
                ))}
              {moves.filter((m) => m.chat_line || m.think_summary).length ===
                0 && (
                <p className="text-xs text-zinc-600">No chat messages yet</p>
              )}
            </div>
          </div>

          {/* Match result */}
          {matchEnd && (
            <div className="rounded-md border border-zinc-700 bg-zinc-900 p-4">
              <h3 className="font-medium text-white">
                {matchEnd.status === "completed" && matchEnd.result === "draw"
                  ? "Draw"
                  : matchEnd.status === "completed"
                    ? "Checkmate"
                    : matchEnd.status === "forfeit"
                      ? "Forfeit"
                      : "Aborted"}
              </h3>
              {matchEnd.reason && (
                <p className="mt-1 text-sm text-zinc-400">{matchEnd.reason}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
