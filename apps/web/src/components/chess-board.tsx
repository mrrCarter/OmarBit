"use client";

import { useMemo, useRef, useEffect, useState } from "react";

// Lichess-style SVG piece paths (cburnett set — public domain)
// Using wiki commons SVG URLs for the standard cburnett chess pieces
const PIECE_SVG: Record<string, string> = {
  K: "https://upload.wikimedia.org/wikipedia/commons/4/42/Chess_klt45.svg",
  Q: "https://upload.wikimedia.org/wikipedia/commons/1/15/Chess_qlt45.svg",
  R: "https://upload.wikimedia.org/wikipedia/commons/7/72/Chess_rlt45.svg",
  B: "https://upload.wikimedia.org/wikipedia/commons/b/b1/Chess_blt45.svg",
  N: "https://upload.wikimedia.org/wikipedia/commons/7/70/Chess_nlt45.svg",
  P: "https://upload.wikimedia.org/wikipedia/commons/4/45/Chess_plt45.svg",
  k: "https://upload.wikimedia.org/wikipedia/commons/f/f0/Chess_kdt45.svg",
  q: "https://upload.wikimedia.org/wikipedia/commons/4/47/Chess_qdt45.svg",
  r: "https://upload.wikimedia.org/wikipedia/commons/f/ff/Chess_rdt45.svg",
  b: "https://upload.wikimedia.org/wikipedia/commons/9/98/Chess_bdt45.svg",
  n: "https://upload.wikimedia.org/wikipedia/commons/e/ef/Chess_ndt45.svg",
  p: "https://upload.wikimedia.org/wikipedia/commons/c/c7/Chess_pdt45.svg",
};

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = ["8", "7", "6", "5", "4", "3", "2", "1"];

// Lichess green color scheme
const LIGHT_SQ = "#ffffdd";
const DARK_SQ = "#86a666";
const COORD_LIGHT = "#86a666";
const COORD_DARK = "#ffffdd";

type Board = (string | null)[][];

function parseFen(fen: string): Board {
  const rows = fen.split(" ")[0].split("/");
  return rows.map((row) => {
    const squares: (string | null)[] = [];
    for (const ch of row) {
      if (ch >= "1" && ch <= "8") {
        squares.push(...Array<null>(Number(ch)).fill(null));
      } else {
        squares.push(ch);
      }
    }
    return squares;
  });
}

function findPieceSquare(
  board: Board,
  piece: string
): [number, number] | null {
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      if (board[r][c] === piece) return [r, c];
    }
  }
  return null;
}

interface ChessBoardProps {
  position: string;
  size?: number;
  lastMove?: { from: string; to: string } | null;
}

export function ChessBoard({
  position,
  size = 360,
  lastMove,
}: ChessBoardProps) {
  const board = useMemo(() => parseFen(position), [position]);
  const prevBoardRef = useRef<Board | null>(null);
  const [animating, setAnimating] = useState<{
    piece: string;
    fromR: number;
    fromC: number;
    toR: number;
    toC: number;
  } | null>(null);

  const sqSize = size / 8;

  // Detect piece movement for animation
  useEffect(() => {
    const prev = prevBoardRef.current;
    if (prev) {
      // Find a piece that moved: appeared on a new square
      for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
          const cur = board[r][c];
          const old = prev[r][c];
          if (cur && cur !== old) {
            // This square gained a piece — find where it came from
            const from = findPieceSquare(prev, cur);
            if (from && (from[0] !== r || from[1] !== c)) {
              // Make sure the source square is now empty or changed
              if (board[from[0]][from[1]] !== cur || (from[0] === r && from[1] === c)) {
                setAnimating({
                  piece: cur,
                  fromR: from[0],
                  fromC: from[1],
                  toR: r,
                  toC: c,
                });
                const timeout = setTimeout(() => setAnimating(null), 150);
                prevBoardRef.current = board;
                return () => clearTimeout(timeout);
              }
            }
          }
        }
      }
    }
    prevBoardRef.current = board;
  }, [board]);

  // Parse lastMove highlight squares
  const highlightSquares = useMemo(() => {
    if (!lastMove) return new Set<string>();
    return new Set([lastMove.from, lastMove.to]);
  }, [lastMove]);

  return (
    <div
      className="relative select-none"
      style={{ width: size, height: size, borderRadius: 3, overflow: "hidden" }}
    >
      {board.flatMap((row, r) =>
        row.map((piece, c) => {
          const isDark = (r + c) % 2 === 1;
          const sqName = `${FILES[c]}${RANKS[r]}`;
          const isHighlighted = highlightSquares.has(sqName);
          const isAnimatingAway =
            animating &&
            animating.fromR === r &&
            animating.fromC === c;

          // Square background
          let bg = isDark ? DARK_SQ : LIGHT_SQ;
          if (isHighlighted) {
            bg = isDark ? "#aaa23a" : "#cdd16a";
          }

          return (
            <div
              key={`${r}-${c}`}
              style={{
                position: "absolute",
                left: c * sqSize,
                top: r * sqSize,
                width: sqSize,
                height: sqSize,
                backgroundColor: bg,
              }}
            >
              {/* Coordinate labels — Lichess style */}
              {c === 0 && (
                <span
                  style={{
                    position: "absolute",
                    top: 2,
                    left: 2,
                    fontSize: sqSize * 0.22,
                    fontWeight: 700,
                    color: isDark ? COORD_DARK : COORD_LIGHT,
                    lineHeight: 1,
                    pointerEvents: "none",
                  }}
                >
                  {RANKS[r]}
                </span>
              )}
              {r === 7 && (
                <span
                  style={{
                    position: "absolute",
                    bottom: 1,
                    right: 3,
                    fontSize: sqSize * 0.22,
                    fontWeight: 700,
                    color: isDark ? COORD_DARK : COORD_LIGHT,
                    lineHeight: 1,
                    pointerEvents: "none",
                  }}
                >
                  {FILES[c]}
                </span>
              )}

              {/* Piece */}
              {piece && !isAnimatingAway && (
                <img
                  src={PIECE_SVG[piece]}
                  alt={piece}
                  draggable={false}
                  style={{
                    width: sqSize * 0.85,
                    height: sqSize * 0.85,
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                    ...(animating &&
                    animating.toR === r &&
                    animating.toC === c
                      ? {
                          transition: "none",
                          animation: "none",
                        }
                      : {}),
                  }}
                />
              )}
            </div>
          );
        })
      )}

      {/* Animated piece sliding to new position */}
      {animating && (
        <img
          src={PIECE_SVG[animating.piece]}
          alt={animating.piece}
          draggable={false}
          style={{
            width: sqSize * 0.85,
            height: sqSize * 0.85,
            position: "absolute",
            zIndex: 10,
            left: animating.toC * sqSize + sqSize * 0.075,
            top: animating.toR * sqSize + sqSize * 0.075,
            transition: "left 150ms ease, top 150ms ease",
            pointerEvents: "none",
          }}
          ref={(el) => {
            if (el) {
              // Start from the old position, then animate to new
              el.style.left = `${animating.fromC * sqSize + sqSize * 0.075}px`;
              el.style.top = `${animating.fromR * sqSize + sqSize * 0.075}px`;
              requestAnimationFrame(() => {
                el.style.left = `${animating.toC * sqSize + sqSize * 0.075}px`;
                el.style.top = `${animating.toR * sqSize + sqSize * 0.075}px`;
              });
            }
          }}
        />
      )}
    </div>
  );
}
