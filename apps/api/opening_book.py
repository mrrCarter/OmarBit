"""Opening detection from move sequences.

Uses a trie of ECO-coded openings to identify the opening name and code
from a list of SAN moves. Covers ~100 common openings.
"""


class OpeningInfo:
    __slots__ = ("eco", "name", "moves")

    def __init__(self, eco: str, name: str, moves: str):
        self.eco = eco
        self.name = name
        self.moves = moves


# Compact opening database: (ECO, name, move_sequence)
# Covers the most common tournament openings.
_OPENINGS: list[tuple[str, str, str]] = [
    # A00-A09: Uncommon Openings
    ("A00", "Polish Opening", "1.b4"),
    ("A01", "Nimzo-Larsen Attack", "1.b3"),
    ("A02", "Bird's Opening", "1.f4"),
    ("A04", "Reti Opening", "1.Nf3"),
    ("A06", "Reti Opening", "1.Nf3 d5 2.g3"),
    ("A09", "Reti Accepted", "1.Nf3 d5 2.c4 d4"),
    # A10-A39: English Opening
    ("A10", "English Opening", "1.c4"),
    ("A13", "English Opening", "1.c4 e6"),
    ("A15", "English Opening: Anglo-Indian", "1.c4 Nf6"),
    ("A20", "English Opening: Reversed Sicilian", "1.c4 e5"),
    ("A30", "English Opening: Symmetrical", "1.c4 c5"),
    # A45-A49: Indian Defenses
    ("A45", "Indian Defense", "1.d4 Nf6"),
    ("A46", "Indian Defense: London System", "1.d4 Nf6 2.Nf3 e6 3.Bf4"),
    # A50-A79: Indian Systems
    ("A50", "Indian Defense", "1.d4 Nf6 2.c4"),
    ("A52", "Budapest Gambit", "1.d4 Nf6 2.c4 e5"),
    ("A56", "Benoni Defense", "1.d4 Nf6 2.c4 c5"),
    ("A57", "Benko Gambit", "1.d4 Nf6 2.c4 c5 3.d5 b5"),
    ("A60", "Benoni Defense: Modern", "1.d4 Nf6 2.c4 c5 3.d5 e6"),
    # A80-A99: Dutch Defense
    ("A80", "Dutch Defense", "1.d4 f5"),
    ("A87", "Dutch Defense: Leningrad", "1.d4 f5 2.c4 Nf6 3.g3 g6"),
    # B00-B09: Uncommon King's Pawn
    ("B00", "Nimzowitsch Defense", "1.e4 Nc6"),
    ("B01", "Scandinavian Defense", "1.e4 d5"),
    ("B02", "Alekhine's Defense", "1.e4 Nf6"),
    ("B03", "Alekhine's Defense: Four Pawns Attack", "1.e4 Nf6 2.e5 Nd5 3.d4 d6 4.c4 Nb6 5.f4"),
    ("B06", "Modern Defense", "1.e4 g6"),
    ("B07", "Pirc Defense", "1.e4 d6 2.d4 Nf6"),
    ("B09", "Pirc Defense: Austrian Attack", "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.f4"),
    # B10-B19: Caro-Kann
    ("B10", "Caro-Kann Defense", "1.e4 c6"),
    ("B12", "Caro-Kann: Advance Variation", "1.e4 c6 2.d4 d5 3.e5"),
    ("B13", "Caro-Kann: Exchange Variation", "1.e4 c6 2.d4 d5 3.exd5 cxd5"),
    ("B14", "Caro-Kann: Panov-Botvinnik Attack", "1.e4 c6 2.d4 d5 3.exd5 cxd5 4.c4"),
    ("B15", "Caro-Kann: Main Line", "1.e4 c6 2.d4 d5 3.Nc3"),
    ("B18", "Caro-Kann: Classical", "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Bf5"),
    # B20-B99: Sicilian Defense
    ("B20", "Sicilian Defense", "1.e4 c5"),
    ("B21", "Sicilian: Smith-Morra Gambit", "1.e4 c5 2.d4 cxd4 3.c3"),
    ("B22", "Sicilian: Alapin", "1.e4 c5 2.c3"),
    ("B23", "Sicilian: Closed", "1.e4 c5 2.Nc3"),
    ("B27", "Sicilian: Hyperaccelerated Dragon", "1.e4 c5 2.Nf3 g6"),
    ("B30", "Sicilian: Old Sicilian", "1.e4 c5 2.Nf3 Nc6"),
    ("B32", "Sicilian: Open", "1.e4 c5 2.Nf3 Nc6 3.d4"),
    ("B33", "Sicilian: Sveshnikov", "1.e4 c5 2.Nf3 Nc6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 e5"),
    ("B35", "Sicilian: Accelerated Dragon", "1.e4 c5 2.Nf3 Nc6 3.d4 cxd4 4.Nxd4 g6"),
    ("B40", "Sicilian: French Variation", "1.e4 c5 2.Nf3 e6"),
    ("B44", "Sicilian: Taimanov", "1.e4 c5 2.Nf3 e6 3.d4 cxd4 4.Nxd4 Nc6"),
    ("B50", "Sicilian", "1.e4 c5 2.Nf3 d6"),
    ("B54", "Sicilian: Open, Dragon/Najdorf", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4"),
    ("B60", "Sicilian: Richter-Rauzer", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 Nc6 6.Bg5"),
    ("B70", "Sicilian: Dragon", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6"),
    ("B72", "Sicilian: Dragon: Classical", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6 6.Be3"),
    ("B76", "Sicilian: Dragon: Yugoslav Attack", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6 6.Be3 Bg7 7.f3"),
    ("B80", "Sicilian: Scheveningen", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 e6"),
    ("B90", "Sicilian: Najdorf", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6"),
    ("B96", "Sicilian: Najdorf, Poisoned Pawn", "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Bg5 e6 7.f4 Qb6"),
    # C00-C19: French Defense
    ("C00", "French Defense", "1.e4 e6"),
    ("C01", "French: Exchange", "1.e4 e6 2.d4 d5 3.exd5 exd5"),
    ("C02", "French: Advance", "1.e4 e6 2.d4 d5 3.e5"),
    ("C03", "French: Tarrasch", "1.e4 e6 2.d4 d5 3.Nd2"),
    ("C10", "French: Rubinstein", "1.e4 e6 2.d4 d5 3.Nc3 dxe4 4.Nxe4"),
    ("C11", "French: Classical", "1.e4 e6 2.d4 d5 3.Nc3 Nf6"),
    ("C15", "French: Winawer", "1.e4 e6 2.d4 d5 3.Nc3 Bb4"),
    ("C18", "French: Winawer, Main Line", "1.e4 e6 2.d4 d5 3.Nc3 Bb4 4.e5 c5"),
    # C20-C29: Open Games (1.e4 e5)
    ("C20", "King's Pawn Game", "1.e4 e5"),
    ("C21", "Center Game", "1.e4 e5 2.d4 exd4"),
    ("C22", "Center Game Accepted", "1.e4 e5 2.d4 exd4 3.Qxd4"),
    ("C23", "Bishop's Opening", "1.e4 e5 2.Bc4"),
    ("C25", "Vienna Game", "1.e4 e5 2.Nc3"),
    ("C26", "Vienna: Falkbeer Variation", "1.e4 e5 2.Nc3 Nf6"),
    # C30-C39: King's Gambit
    ("C30", "King's Gambit", "1.e4 e5 2.f4"),
    ("C33", "King's Gambit Accepted", "1.e4 e5 2.f4 exf4"),
    ("C36", "King's Gambit: Abbazia Defense", "1.e4 e5 2.f4 exf4 3.Nf3 d5"),
    # C40-C49: Open Games
    ("C40", "King's Knight Opening", "1.e4 e5 2.Nf3"),
    ("C41", "Philidor Defense", "1.e4 e5 2.Nf3 d6"),
    ("C42", "Petrov's Defense", "1.e4 e5 2.Nf3 Nf6"),
    ("C44", "Scotch Game", "1.e4 e5 2.Nf3 Nc6 3.d4"),
    ("C45", "Scotch Game", "1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4"),
    ("C46", "Three Knights Game", "1.e4 e5 2.Nf3 Nc6 3.Nc3"),
    ("C47", "Four Knights Game", "1.e4 e5 2.Nf3 Nc6 3.Nc3 Nf6"),
    ("C50", "Italian Game", "1.e4 e5 2.Nf3 Nc6 3.Bc4"),
    ("C51", "Evans Gambit", "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.b4"),
    ("C53", "Italian Game: Classical", "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5"),
    ("C54", "Italian Game: Giuoco Piano", "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3"),
    ("C55", "Two Knights Defense", "1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6"),
    # C60-C99: Ruy Lopez
    ("C60", "Ruy Lopez", "1.e4 e5 2.Nf3 Nc6 3.Bb5"),
    ("C63", "Ruy Lopez: Schliemann", "1.e4 e5 2.Nf3 Nc6 3.Bb5 f5"),
    ("C65", "Ruy Lopez: Berlin", "1.e4 e5 2.Nf3 Nc6 3.Bb5 Nf6"),
    ("C69", "Ruy Lopez: Exchange", "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Bxc6"),
    ("C70", "Ruy Lopez: Morphy", "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6"),
    ("C78", "Ruy Lopez: Archangel", "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O b5"),
    ("C80", "Ruy Lopez: Open", "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Nxe4"),
    ("C84", "Ruy Lopez: Closed", "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7"),
    ("C88", "Ruy Lopez: Anti-Marshall",  # noqa: E501
     "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 O-O 8.a4"),
    ("C89", "Ruy Lopez: Marshall Attack", "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 O-O 8.c3 d5"),
    # D00-D05: Queen's Pawn
    ("D00", "Queen's Pawn Game", "1.d4 d5"),
    ("D01", "Richter-Veresov Attack", "1.d4 d5 2.Nc3 Nf6 3.Bg5"),
    ("D02", "London System", "1.d4 d5 2.Nf3 Nf6 3.Bf4"),
    ("D04", "Colle System", "1.d4 d5 2.Nf3 Nf6 3.e3"),
    ("D05", "Colle System", "1.d4 d5 2.Nf3 Nf6 3.e3 e6 4.Bd3"),
    # D06-D09: Queen's Gambit
    ("D06", "Queen's Gambit", "1.d4 d5 2.c4"),
    ("D07", "Chigorin Defense", "1.d4 d5 2.c4 Nc6"),
    ("D08", "Queen's Gambit: Albin Counter-Gambit", "1.d4 d5 2.c4 e5"),
    ("D10", "Slav Defense", "1.d4 d5 2.c4 c6"),
    ("D15", "Slav: Main Line", "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3"),
    ("D20", "Queen's Gambit Accepted", "1.d4 d5 2.c4 dxc4"),
    ("D30", "Queen's Gambit Declined", "1.d4 d5 2.c4 e6"),
    ("D35", "QGD: Exchange", "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.cxd5"),
    ("D37", "QGD: Classical", "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Nf3"),
    ("D43", "Semi-Slav Defense", "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 e6"),
    ("D46", "Semi-Slav: Meran", "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 e6 5.e3 Nbd7 6.Bd3"),
    # E00-E09: Catalan
    ("E00", "Catalan Opening", "1.d4 Nf6 2.c4 e6 3.g3"),
    ("E04", "Catalan: Open", "1.d4 Nf6 2.c4 e6 3.g3 d5 4.Bg2 dxc4"),
    ("E06", "Catalan: Closed", "1.d4 Nf6 2.c4 e6 3.g3 d5 4.Bg2 Be7"),
    # E10-E19: Queen's Indian
    ("E10", "Queen's Indian Defense", "1.d4 Nf6 2.c4 e6 3.Nf3"),
    ("E12", "Queen's Indian", "1.d4 Nf6 2.c4 e6 3.Nf3 b6"),
    ("E15", "Queen's Indian: Fianchetto", "1.d4 Nf6 2.c4 e6 3.Nf3 b6 4.g3"),
    # E20-E59: Nimzo-Indian
    ("E20", "Nimzo-Indian Defense", "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4"),
    ("E32", "Nimzo-Indian: Classical", "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.Qc2"),
    ("E41", "Nimzo-Indian: Huebner", "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.e3 c5"),
    ("E46", "Nimzo-Indian: Reshevsky", "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.e3 O-O"),
    # E60-E99: King's Indian
    ("E60", "King's Indian Defense", "1.d4 Nf6 2.c4 g6"),
    ("E62", "King's Indian: Fianchetto", "1.d4 Nf6 2.c4 g6 3.g3 Bg7 4.Bg2 d6 5.Nf3"),
    ("E70", "King's Indian: Classical", "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4"),
    ("E73", "King's Indian: Averbakh", "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Be2 O-O 6.Bg5"),
    ("E76", "King's Indian: Four Pawns Attack", "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.f4"),
    ("E80", "King's Indian: Saemisch", "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.f3"),
    ("E90", "King's Indian: Classical Main Line", "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3"),
    ("E97", "King's Indian: Mar del Plata", "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 7.O-O Nc6"),
    ("E99", "King's Indian: Classical Main",  # noqa: E501
     "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 7.O-O Nc6 8.d5 Ne7"),
    # Grunfeld
    ("D70", "Grunfeld Defense", "1.d4 Nf6 2.c4 g6 3.Nc3 d5"),
    ("D80", "Grunfeld: Exchange", "1.d4 Nf6 2.c4 g6 3.Nc3 d5 4.cxd5 Nxd5"),
    ("D85", "Grunfeld: Exchange, Main Line", "1.d4 Nf6 2.c4 g6 3.Nc3 d5 4.cxd5 Nxd5 5.e4 Nxc3 6.bxc3 Bg7"),
]


def _parse_moves(move_text: str) -> list[str]:
    """Parse a move string like '1.e4 e5 2.Nf3 Nc6' into ['e4', 'e5', 'Nf3', 'Nc6']."""
    import re
    # Remove move numbers: "1." "2." etc.
    cleaned = re.sub(r"\d+\.", "", move_text)
    return cleaned.split()


# Build trie at import time for O(1) lookups
# Key: tuple of SAN moves, Value: OpeningInfo
_OPENING_TRIE: dict[tuple[str, ...], OpeningInfo] = {}

for eco, name, moves_str in _OPENINGS:
    parsed = tuple(_parse_moves(moves_str))
    _OPENING_TRIE[parsed] = OpeningInfo(eco, name, moves_str)


def detect_opening(moves: list[str]) -> OpeningInfo | None:
    """Detect the opening from a list of SAN moves.

    Returns the most specific (longest) matching opening, or None if
    no opening is recognized.
    """
    best: OpeningInfo | None = None
    for length in range(1, min(len(moves) + 1, 30)):
        prefix = tuple(moves[:length])
        if prefix in _OPENING_TRIE:
            best = _OPENING_TRIE[prefix]
    return best
