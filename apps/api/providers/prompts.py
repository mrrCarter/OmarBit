"""Shared prompt templates for AI chess provider requests.

Per spec Section 5.2 (Thought-Stream Contract):
- Request a 1-2 sentence strategic summary, not reasoning trace
- Never request or store raw chain-of-thought
"""

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
    style_instruction = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["balanced"])
    ply = match_context.get("ply", 0)
    color = "White" if ply % 2 == 0 else "Black"

    return (
        f"Position (FEN): {fen}\n"
        f"Legal moves: {', '.join(legal_moves)}\n"
        f"You are playing as {color}.\n"
        f"Style: {style_instruction}\n"
        f"Move number: {ply // 2 + 1}\n"
        "Respond with the JSON object only."
    )
