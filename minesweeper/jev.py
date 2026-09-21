"""Jev chooses a Minesweeper click through the Vercel AI Gateway."""
import json
import os
import random
import time
import urllib.error
import urllib.request

from .game import COLS, COVERED, ROWS

URL = "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"
GOAL = ("Beginner Minesweeper on a 9 by 9 board with 10 mines. A number says exactly how many of its eight "
        "neighbors are mines. Covered squares are unknown. Click a covered square; a mine loses immediately. "
        "Reveal every safe square to win. Infer safe squares from the visible clues; never assume hidden information.")


def label(cell):
    return f"{chr(65 + cell[1])}{cell[0] + 1}"


def board_text(board):
    lines = ["    " + " ".join(chr(65 + c) for c in range(COLS))]
    for r in range(ROWS):
        cells = ["#" if board[r, c] == COVERED else str(int(board[r, c])) for c in range(COLS)]
        lines.append(f"{r + 1:>2}  " + " ".join(cells))
    return "\n".join(lines)


def request_body(board, cells):
    return {"state": {"game": GOAL, "board": board_text(board), "notation": "# means covered; A1 is row 1 column A."},
            "questions": {"click": {"type": "choice", "instructions": "Choose the safest covered square. Prioritize logically guaranteed safe squares.",
                                      "criteria": {label(x): f"Click {label(x)} (row {x[0] + 1}, column {chr(65 + x[1])})." for x in cells}}}}


def ask(body, key=None, attempts=12):
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {key or os.environ['AI_GATEWAY_API_KEY']}", "content-type": "application/json",
               "ai-gateway-protocol-version": "0.0.1", "ai-evaluation-model-specification-version": "4",
               "ai-model-id": "typesafe-ai/jev"}
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if getattr(error, "code", None) not in (None, 429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            time.sleep(0.3 + random.random() * 0.3 + attempt * 0.35)


def jev_move(board, cells, key=None):
    result = ask(request_body(board, cells), key)
    answer = result["answers"]["click"]
    probabilities = answer.get("probabilities") or {answer["choice"]: 1.0}
    choice = max(probabilities, key=probabilities.get)
    lookup = {label(x): x for x in cells}
    return lookup[choice], float(probabilities[choice]), (result.get("usage") or {}).get("inputTokens", 0)

