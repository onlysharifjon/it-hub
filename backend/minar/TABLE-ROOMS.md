# Student online rooms

Chess and English checkers require two students. UNO supports 2–6 students;
Mafia supports 6–10. Sudoku is private solo play. There are no automated players.
Rooms are invitation-only: share the eight-character code. API access always
requires the student session and normal origin checks.

POST /space/tables creates a room; GET /space/tables?game=chess resumes the
caller's active room. POST /space/tables/{code}/join joins by code.
GET /space/tables/{code} returns only that participant's safe projection.
POST /space/tables/{code}/actions takes type, version and requestId. The caller
account is locked before the room. Successful requests retain a receipt and
increment the room version. Stale moves return 409; exact retries are idempotent.

Clients poll every 1.8 seconds while visible and resume after refresh. Room state,
hands, roles, membership and results survive API restarts. Lobbies expire after
30 minutes and games after two hours. Chess/checkers/UNO turns allow five minutes;
Mafia phases allow 90 seconds. Authenticated tick actions advance the server clock.
Leaving an active room or a turn timeout ends the round without rewards. Going
back to the catalog leaves the room available to resume.

The server decides legal moves and winners. A finished room is claimed through
the existing /games/results endpoint with roomId; a unique table:<UUID> result
prevents duplicate rewards. Only verified natural wins qualify for 2 lightning
and 5 XP, at most three times per game per local day. Coins are never awarded.
Draws, abandoned games and timeouts cannot manufacture reward wins.

Chess uses python-chess for castling, en passant, promotion, king safety and
checkmate. Repetition/50-move draw claims are automatic in this room variant.
Checkers uses forward captures for ordinary men, short kings, mandatory capture,
multiple jumps, crowning ending the turn, and repetition/no-progress draws.
UNO is a single-round, no-stacking variant. +4 requires no matching-color card;
UNO must be selected with the penultimate card, otherwise two cards are drawn.
Mafia keeps every role and night choice private; a detective sees only their own
investigations. Discussion is a bounded room-local text chat, rendered as text.
Sudoku is generated on the server with exactly one solution; only givens and the
saved draft are exposed, never the solution.

Rule references: https://python-chess.readthedocs.io/en/latest/core.html and
https://service.mattel.com/instruction_sheets/41940-Eng.pdf
