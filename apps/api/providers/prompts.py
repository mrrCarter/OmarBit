"""Shared prompt templates for AI chess provider requests.

Per spec Section 5.2 (Thought-Stream Contract):
- Request a 1-2 sentence strategic summary, not reasoning trace
- Never request or store raw chain-of-thought
"""

import re

# FEN validation: 8 ranks separated by /, then side/castling/ep/halfmove/fullmove
_FEN_RE = re.compile(
    r"^[rnbqkpRNBQKP1-8/]+ [wb] [KQkq-]+ [a-h1-8-]+ \d+ \d+$"
)

# SAN validation: covers standard moves, castling, promotions
_SAN_RE = re.compile(
    r"^([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?|O-O(-O)?[+#]?)$"
)


def validate_fen(fen: str) -> str:
    """Sanitize FEN: strip control chars, validate format."""
    clean = fen.replace("\n", "").replace("\r", "").strip()
    if len(clean) > 200 or not _FEN_RE.match(clean):
        raise ValueError(f"Invalid FEN format: {clean[:50]}")
    return clean


def validate_san_list(moves: list[str]) -> list[str]:
    """Validate each move matches SAN format."""
    validated = []
    for m in moves:
        m = m.strip()
        if not _SAN_RE.match(m):
            raise ValueError(f"Invalid SAN move: {m[:20]}")
        validated.append(m)
    return validated


SYSTEM_PROMPT = (
    "You are a chess-playing AI in the OmarBit Sentinel Chess Arena. "
    "You will be given a chess position (FEN) and a list of legal moves (SAN). "
    "You must respond with EXACTLY a JSON object with these fields:\n"
    '  "move": one of the legal moves (SAN notation)\n'
    '  "think_summary": a 1-2 sentence strategic summary of your reasoning (max 500 chars, no raw chain-of-thought)\n'
    '  "chat_line": an optional short spectator-facing message (max 280 chars, teen-safe, English only)\n\n'
    "Rules:\n"
    "- You MUST pick a move from the legal_moves list.\n"
    "- Do NOT include reasoning traces, scratchpad, or chain-of-thought.\n"
    "- The think_summary should be a concise strategic insight.\n"
    "- The chat_line should be entertaining, sportsmanlike, and appropriate for ages 13+.\n"
    "- Respond with ONLY the JSON object, no markdown fences or extra text."
)

STYLE_INSTRUCTIONS: dict[str, str] = {
    "aggressive": "Play aggressively: prioritize attacks, sacrifices, and tactical combinations.",
    "positional": "Play positionally: focus on pawn structure, piece placement, and long-term advantages.",
    "balanced": "Play a balanced game: mix tactical and positional play as the position demands.",
    "chaotic": "Play chaotically: choose surprising, unconventional moves that create complex positions.",
    "defensive": "Play defensively: prioritize solid structures, safety, and counterattacking opportunities.",
}


def build_user_prompt(
    fen: str,
    legal_moves: list[str],
    style: str,
    match_context: dict,
) -> str:
    safe_fen = validate_fen(fen)
    safe_moves = validate_san_list(legal_moves)
    style_instruction = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["balanced"])
    ply = match_context.get("ply", 0)
    is_white = match_context.get("is_white", ply % 2 == 0)
    color = "White" if is_white else "Black"
    your_name = match_context.get("white_name", "White") if is_white else match_context.get("black_name", "Black")
    opponent_name = match_context.get("black_name", "Black") if is_white else match_context.get("white_name", "White")
    white_time = match_context.get("white_time", 300)
    black_time = match_context.get("black_time", 300)

    return (
        f"Position (FEN): {safe_fen}\n"
        f"Legal moves: {', '.join(safe_moves)}\n"
        f"You are: {your_name} (playing as {color})\n"
        f"Opponent: {opponent_name}\n"
        f"Time remaining — You: {white_time:.0f}s, Opponent: {black_time:.0f}s\n"
        f"Style: {style_instruction}\n"
        f"Move number: {ply // 2 + 1}\n"
        "Respond with the JSON object only."
    )
