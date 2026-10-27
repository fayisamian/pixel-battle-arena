# File Changelog — Final Completion Pass

No files were deleted. The project already had uncommitted files in this workspace before this pass; this list records the files changed or added for this completion work.

## Modified

- `.gitignore` — ignore local `.env` files while allowing checked-in `.env.example` templates.
- `README.md` — replace the earlier quick-start notes with full local setup, configuration, tests, production build, deployment, and troubleshooting guidance.
- `backend/app.py` — validate WebSocket browser origins against `PIXEL_BATTLE_ALLOWED_ORIGINS` and return a readable rejection message.
- `backend/rooms.py` — reject stale or mismatched resume tokens instead of treating them as fresh players or allowing a stale host tab to recreate a room; factor one update sweep into `update_rooms()` for direct testing; log WebSocket state-send failures.
- `frontend/.gitignore` — ignore frontend-local environment files while allowing the example template.
- `frontend/src/App.css` — style the host badge in the arena scoreboard.
- `frontend/src/screens/ArenaScreen.tsx` — display the server-reported host role on the scoreboard during a match.

## Added

- `backend/.env.example` — document backend match-duration and allowed-origin configuration.
- `backend/tests/test_rooms.py` — add ten standard-library backend regression tests for reconnect, host transfer, stale tokens, expiry/cleanup, immediate leave, socket replacement, capacity, room isolation, movement, scoring, ties, and restart.
- `backend/tests/websocket_smoke.py` — add a repeatable runnable integration check for two-client movement/scoring, in-match reconnect, host promotion, match completion/restart, invalid rooms, origin validation, capacity, and room isolation.
- `frontend/.env.example` — document the frontend WebSocket base URL.
- `LEARNING_GUIDE.md` — explain the current architecture, important files, data flow, game loop, reconnect rules, setup, build, troubleshooting, movement trace, and glossary.
- `FILE_CHANGELOG.md` — record all files changed or added by this pass.


## Maps, collisions, and scoring pass

### Modified

- `README.md` — add map selection, obstacle rules, point values, and updated manual multiplayer checks.
- `backend/app.py` — accept the host's `select_map` WebSocket message and report validation errors.
- `backend/rooms.py` — store selected map IDs, use server map spawns, broadcast map data and score events, block obstacle movement with axis sliding, award 10 per coin, and apply non-repeating hazard/danger penalties that clamp scores at zero.
- `backend/tests/test_rooms.py` — update coin scoring expectations and add checks for walls, edges, map loading and selection, synchronized map snapshots, and penalty behavior.
- `backend/tests/websocket_smoke.py` — verify two clients receive the selected map and see synchronized 10-point coin scoring.
- `frontend/src/App.css` — style four lobby map previews, map-themed arena surfaces, obstacles, hazards, coins, player sizes, and score feedback for narrow screens.
- `frontend/src/App.tsx` — connect map selection, map snapshots, and score events to the lobby and arena.
- `frontend/src/hooks/useRoomSocket.ts` — send map-selection messages and parse map/score state from the server.
- `frontend/src/screens/ArenaScreen.tsx` — render server map geometry, theme, score feedback, and movement controls with geometry aligned to the server's 960 by 540 arena.
- `frontend/src/screens/LobbyScreen.tsx` — show the selected map and host-only map choices to every player.
- `frontend/src/types.ts` — describe map, collision area, and scoring event data.
- `LEARNING_GUIDE.md` — document map configuration, collision, scoring, map selection, and the current game loop.
- `FILE_CHANGELOG.md` — add this maps and gameplay pass to the project change record.

### Added

- `backend/maps.py` — define the four server-owned maps and validate player spawn positions.
