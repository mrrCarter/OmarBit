import { describe, expect, it } from "vitest";
import type { ReplayData, ReplayMove } from "@/lib/replay-cache";

describe("ReplayData types", () => {
  it("should define ReplayMove structure", () => {
    const move: ReplayMove = {
      ply: 1,
      san: "e4",
      fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
      eval_cp: 30,
      think_summary: "King's pawn opening",
      chat_line: "Let's go!",
      timestamp: "2025-01-01T00:00:00Z",
    };
    expect(move.ply).toBe(1);
    expect(move.san).toBe("e4");
  });

  it("should define ReplayData structure", () => {
    const data: ReplayData = {
      match: {
        id: "test-id",
        white_ai_id: "w-id",
        black_ai_id: "b-id",
        time_control: "5+0",
        status: "completed",
        winner_ai_id: "w-id",
        forfeit_reason: null,
        pgn: null,
        created_at: "2025-01-01T00:00:00Z",
        completed_at: "2025-01-01T01:00:00Z",
      },
      moves: [],
      content_hash: "abc123",
      move_count: 0,
    };
    expect(data.match.status).toBe("completed");
    expect(data.content_hash).toBe("abc123");
  });

  it("should allow null optional fields", () => {
    const move: ReplayMove = {
      ply: 1,
      san: "e4",
      fen: "test-fen",
      eval_cp: null,
      think_summary: null,
      chat_line: null,
      timestamp: "2025-01-01T00:00:00Z",
    };
    expect(move.eval_cp).toBeNull();
    expect(move.think_summary).toBeNull();
    expect(move.chat_line).toBeNull();
  });
});
