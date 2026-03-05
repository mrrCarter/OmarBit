"use client";

const PIECE_UNICODE: Record<string, string> = {
  K: "\u2654", Q: "\u2655", R: "\u2656", B: "\u2657", N: "\u2658", P: "\u2659",
  k: "\u265A", q: "\u265B", r: "\u265C", b: "\u265D", n: "\u265E", p: "\u265F",
};

function parseFen(fen: string): (string | null)[][] {
  const rows = fen.split(" ")[0].split("/");
  return rows.map((row) => {
    const squares: (string | null)[] = [];
    for (const ch of row) {
      if (ch >= "1" && ch <= "8") {
        squares.push(...Array(Number(ch)).fill(null));
      } else {
        squares.push(ch);
      }
    }
    return squares;
  });
}

interface ChessBoardProps {
  position: string;
  size?: number;
}

export function ChessBoard({ position, size = 360 }: ChessBoardProps) {
  const board = parseFen(position);
  const sqSize = size / 8;

  return (
    <div
      className="grid grid-cols-8 overflow-hidden rounded-sm border border-zinc-700"
      style={{ width: size, height: size }}
    >
      {board.flatMap((row, r) =>
        row.map((piece, c) => {
          const isDark = (r + c) % 2 === 1;
          return (
            <div
              key={`${r}-${c}`}
              className={isDark ? "bg-zinc-600" : "bg-zinc-400"}
              style={{
                width: sqSize,
                height: sqSize,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {piece && (
                <span
                  style={{ fontSize: sqSize * 0.7, lineHeight: 1 }}
                  className="select-none"
                >
                  {PIECE_UNICODE[piece] ?? ""}
                </span>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
