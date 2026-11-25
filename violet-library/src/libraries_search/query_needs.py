"""Extract only plainly stated reading needs from a free-text book request."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryNeeds:
    """Small, explainable hints; absence means unknown rather than a default."""

    level: str | None = None
    wants_examples: bool = False
    wants_methods: bool = False
    wants_practical: bool = False
    avoids_code: bool = False
    avoids_math: bool = False


_INTRO = re.compile(
    r"\b(?:beginner|introductory|introduction|intro\b|new to|starting|"
    r"sencillo|sencilla|nivel inicial|principiante|je commence|débutant|débutante|"
    r"einführung|verständlich)\b", re.I
)
_ADVANCED = re.compile(
    r"\b(?:graduate|master'?s|masters|thesis|dissertation|seminar|"
    r"maestría|tesis|mémoire|masterarbeit|doktorarbeit)\b", re.I
)
_EXAMPLES = re.compile(
    r"\b(?:examples?|case studies|cases|ejemplos?|casos|exemples?|"
    r"études de cas|beispiele?|fallstudien)\b", re.I
)
_METHODS = re.compile(
    r"\b(?:methods?|methodology|techniques?|métodos?|metodología|"
    r"méthodes?|methoden|methodik)\b", re.I
)
_PRACTICAL = re.compile(
    r"\b(?:practical|hands.on|in practice|applied|práctic[oa]s?|pratique|"
    r"praktisch|praxis)\b", re.I
)
_NO_CODE = re.compile(
    r"\b(?:no|not|without|don'?t|can't|cannot|little|less)\b"
    r".{0,22}\b(?:code|coding|programming|python)\b", re.I
)
_NO_MATH = re.compile(
    r"\b(?:no|not|without|little|less|limited)\b"
    r".{0,24}\b(?:math|mathematics|equations?|calculus|formulas?)\b", re.I
)


def parse_query_needs(query: str) -> QueryNeeds:
    """Find explicit needs while leaving the complete query intact for meaning search."""
    text = query.strip()
    intro, advanced = bool(_INTRO.search(text)), bool(_ADVANCED.search(text))
    level = None
    if intro != advanced:
        level = "introductory" if intro else "advanced"
    return QueryNeeds(
        level=level,
        wants_examples=bool(_EXAMPLES.search(text)),
        wants_methods=bool(_METHODS.search(text)),
        wants_practical=bool(_PRACTICAL.search(text)),
        avoids_code=bool(_NO_CODE.search(text)),
        avoids_math=bool(_NO_MATH.search(text)),
    )
