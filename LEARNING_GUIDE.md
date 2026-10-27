# Pixel Battle Arena — Learning Guide

This guide follows the code currently in this project. The short version is: React displays the game and sends player intent; FastAPI owns the rooms, selected maps, positions, coins, scores, and clock. The browser never decides that a move or coin pickup succeeded.

## 1. Frontend and backend

The **frontend** is the web page players see. React components render the home page, lobby, arena, and results screen. TypeScript describes the shapes of messages and helps catch mistakes while building. Vite serves the app during development and creates the production files in `frontend/dist`.

The **backend** is the Python program that runs the match. FastAPI accepts WebSocket connections. `RoomManager` in `backend/rooms.py` keeps the rooms in a Python dictionary and changes their game state. The server process is the source of truth for every player position, score, coin, host, and match time.

There is no account system and no database. Room state exists only in backend memory. If that process stops or restarts, its rooms are lost.

## 2. Important project files

### Project root

- `README.md` — setup, configuration, test, and deployment instructions.
- `LEARNING_GUIDE.md` — this code walkthrough.
- `FILE_CHANGELOG.md` — the files changed during the project completion and maps/gameplay passes.
- `.gitignore` — keeps virtual environments, dependencies, build output, and local environment files out of Git.

### Backend

- `backend/app.py` — creates the FastAPI `app`; `lifespan()` starts and stops the room update task; `room_websocket()` validates the browser's join and movement messages, handles host map selection, and manages the WebSocket conversation; `send_error()` sends a readable error before closing the socket.
- `backend/maps.py` — defines the four server-owned map layouts, themes, obstacle rectangles, hazard and danger areas, coin spawn points, and valid player spawns. `get_map()` loads a map by ID and `valid_spawn()` checks that a spawn is inside the arena and outside solid walls.
- `backend/rooms.py` — defines `Player`, `Coin`, and `Room`; `RoomManager.add_player()` joins or resumes a player; `select_map()` checks that only the host changes a lobby map; `broadcast()` sends room snapshots; `set_input()` records direction keys; `start_match()` validates and loads the selected map; `update_room()` applies wall and arena-edge collision, coin scoring, penalty cooldowns, and the timer; `_mark_disconnected()` records disconnects and transfers host status; `_expire_disconnected()` removes players after the grace period; `leave()` removes an intentional leaver; `update_loop()` runs the server tick; `update_rooms()` performs one cleanup and update pass.
- `backend/requirements.txt` — Python packages required by the backend: FastAPI and Uvicorn.
- `backend/.env.example` — example backend settings. Python does not load this file automatically; set the variables in your terminal or hosting dashboard.
- `backend/tests/test_rooms.py` — standard-library `unittest` regression tests for room limits, isolation, reconnects, host changes, cleanup, movement, scoring, timer completion, ties, leave, and restart.
- `backend/tests/websocket_smoke.py` — a live WebSocket smoke test that connects multiple clients to an already-running backend and checks synchronized map selection, movement, coin pickup, refresh recovery, host transfer, match restart, validation, capacity, and separate rooms.

### Frontend

- `frontend/package.json` — JavaScript dependencies and commands such as `npm run dev` and `npm run build`.
- `frontend/package-lock.json` — exact dependency versions selected by npm.
- `frontend/.env.example` — example for `VITE_WS_BASE_URL`, the WebSocket address embedded in the frontend at build time.
- `frontend/index.html` — the HTML page Vite loads.
- `frontend/vite.config.ts` — configures the React plugin for Vite.
- `frontend/src/main.tsx` — attaches the React `App` component to the page and enables React Strict Mode.
- `frontend/src/App.tsx` — chooses which screen to show, saves enough room details in tab session storage to recover after refresh, and passes live room data to each screen.
- `frontend/src/hooks/useRoomSocket.ts` — opens the browser WebSocket, sends the join message and movement commands, stores the resume token, receives server state, and retries unexpected connection closes.
- `frontend/src/types.ts` — TypeScript definitions for movement keys, players, coins, snapshots, and connection status.
- `frontend/src/screens/HomeScreen.tsx` — player name, create-room, and join-room form.
- `frontend/src/screens/LobbyScreen.tsx` — room code, connected players, host label, connection status, start button, and leave button.
- `frontend/src/screens/ArenaScreen.tsx` — arena, player sprites, coins, scores, timer, keyboard controls, and press-and-hold touch controls. It shows the current host on the scoreboard.
- `frontend/src/screens/ResultsScreen.tsx` — final scores, winner or tie, and host-only restart control.
- `frontend/src/App.css` and `frontend/src/index.css` — component and global styling, including responsive layouts.
- `frontend/src/vite-env.d.ts` — tells TypeScript about Vite environment variables such as `VITE_WS_BASE_URL`.
- `frontend/tsconfig*.json` — TypeScript compiler settings used by the production build.

## 3. HTTP and WebSocket connection

HTTP is the ordinary request-and-response protocol used for web pages and API calls. The browser loads the frontend over HTTP/HTTPS. The root backend health check, `GET /`, responds with a small JSON message.

A WebSocket starts with an HTTP upgrade, then keeps a two-way connection open. The browser can send a message at any time, and the server can send updated game state without waiting for a new HTTP request. The game connects to `/ws/{room_code}`. Local development usually uses `ws://localhost:8000`; a secure public site uses `wss://`.

`room_websocket()` in `backend/app.py` accepts the socket, checks the browser `Origin` against `PIXEL_BATTLE_ALLOWED_ORIGINS`, then waits for a JSON `join` message. Once accepted, both sides exchange small JSON messages such as `join`, `input`, `start_match`, `leave`, `joined`, `state`, and `error`.

## 4. How a room and player are created

1. `HomeScreen` calls `handleCreateRoom()` or `handleJoinRoom()` in `App.tsx`.
2. The app creates a six-character code for the host, or normalizes the code a guest typed. It saves the code, player name, and original role in `sessionStorage` so a browser refresh can return to that screen.
3. `useRoomSocket()` opens `/ws/{room_code}` and sends `{ type: "join", name, isHost }`. If this tab has a saved resume token for that room, it includes `resumeToken` too.
4. `room_websocket()` validates the room code and message, then calls `RoomManager.add_player()`.
5. A new host creates a `Room`. A guest can join only a room that exists. The room stores players in a dictionary keyed by their temporary player IDs. A room can contain up to eight players.
6. A new player receives a random temporary ID and a 128-bit random resume token. The server sends both in the `joined` message. The browser stores the token in tab-scoped session storage.
7. `RoomManager.broadcast()` sends the current room snapshot to everyone connected in that room.

The token is looked up only inside the room named by the WebSocket URL. An expired, missing, or mismatched token cannot be used as a fresh join or to recreate a room. The player must return home and join/create again.

## 5. How keyboard movement reaches the server

The server does not accept a browser-supplied position. The browser sends only the directions the player currently holds.

In `ArenaScreen.tsx`, `handleKeyDown()` translates W/A/S/D or the arrow keys into `up`, `left`, `down`, or `right`. `sendCurrentKeys()` combines keyboard keys with held touch keys and calls `onMovement`. `App.tsx` passes `room.sendMovement` into that callback. In `useRoomSocket.ts`, `sendMovement()` sends a JSON message like:

```json
{"type":"input","keys":["right","up"]}
```

The server validates the directions in `room_websocket()` and calls `RoomManager.set_input()`. That stores current and newly pressed keys on the server-side `Player` object. The server's `update_loop()` wakes every `UPDATE_SECONDS` (currently 1/20 second) and calls `update_rooms()`, which invokes `update_room()` for a live match. `update_room()` computes speed and diagonal movement on the server, clamps the player box to the arena edges, and tests each movement axis against the selected map's solid rectangles. If one axis hits a wall, the other axis can still move, which lets a player slide along corners.

## 6. Coins, collisions, score, and broadcast

`backend/maps.py` defines Grasslands Arena, Desert Ruins, Neon Cyber Arena, and Frozen Labyrinth. Each `ArenaMap` holds the map theme, arena dimensions, solid obstacle rectangles, hazards, danger zones, and separate spawn points for players and coins. The browser receives the selected map in each room snapshot so it can draw the same geometry the server uses for collision.

The host sends a `select_map` WebSocket message from `LobbyScreen.tsx`. `room_websocket()` calls `RoomManager.select_map()`, which rejects non-host selections, unknown map IDs, and changes after a match starts. When the host starts a match, `start_match()` checks the selected map and valid spawn points before resetting player positions and filling the room with coins.

On each game tick, `update_room()` moves every player based on the server's stored keys and prevents the player rectangle from entering a solid obstacle. It compares each player's center with coin locations; collecting one removes it, adds 10 points, and creates a replacement at a configured spawn point. Touching a hazard removes 10 points, and touching a danger zone removes 5. Scores never fall below zero. Each zone triggers once per continuous overlap, with a short server cooldown before it can trigger again after the player leaves and re-enters. Short-lived score events are included in state snapshots so every client can display the same feedback. The browser cannot report a position or score directly.

`update_rooms()` calls `broadcast()` during a match. `RoomManager._snapshot()` packages the same players, host and connection flags, scores, coins, selected map, available map names, collision areas, temporary score events, match status, timer, and winner IDs for each room. `useRoomSocket()` parses a `state` message into React state. React renders the new positions, score, coins, and time in `ArenaScreen.tsx`.

## 7. Timer, game over, and restart

`RoomManager.start_match()` records `match_ends_at` using Python's monotonic clock plus `MATCH_DURATION_SECONDS`. A monotonic clock measures elapsed time and is not affected by the computer clock being adjusted.

At each `update_room()` tick, the server checks that deadline. When time is up, it changes the room status to `finished`, clears the match clock and coins, and stops movement. `_snapshot()` finds all players with the top score; if several players share it, they are all included in `winnerIds`, so the result is a tie.

`App.tsx` switches to `ResultsScreen` when the server reports `finished`. The screen shows final scores and the winner. Only the currently connected host sees **Play again**. That button sends `start_match`; `start_match()` resets positions, scores, timer, and coins for every player in the room.

## 8. Disconnect, reconnect, host transfer, and cleanup

When a WebSocket closes unexpectedly, `room_websocket()` reaches its `finally` block and calls `RoomManager.disconnect()`. `_mark_disconnected()` checks that the disconnect belongs to the player's current socket, marks the player offline, records the time, and clears held keys. The player record remains for 30 seconds so a refresh can reconnect.

The browser keeps the token in `sessionStorage`, which survives a refresh in the same browser tab. On reconnect, `add_player()` finds that token in the same room and reattaches the socket to the existing `Player` object. That preserves its ID, position, score, and current role. If a newer socket replaces an older socket, the server closes the old one; the identity check in `disconnect()` prevents that stale socket from removing the new connection.

Host transfer is immediate and consistent: if a host disconnects, `_mark_disconnected()` transfers host status to the first other connected player. If the original host returns while another host is connected, the returning player remains a guest. If no connected host remains, a returning player can become host. `state` snapshots carry `isHost` to all players; the lobby uses it for host controls, the arena scoreboard now makes it visible, and the results screen uses it to gate restart.

After 30 seconds, `_expire_disconnected()` removes an offline player. `update_rooms()` removes a room once it contains no players. Choosing **Leave room** sends `leave`; `RoomManager.leave()` removes that player immediately and promotes a new host if needed.

## 9. React state and screens

`useRoomSocket()` is the bridge between WebSocket messages and React. It holds connection status, the current player ID, the latest room snapshot, and error text in React state. When it receives a `state` message, its state setters cause React to render again.

`App.tsx` decides whether the player should see `HomeScreen`, `LobbyScreen`, `ArenaScreen`, or `ResultsScreen`. It derives host status from the latest server player list rather than trusting a browser-only role. Each screen receives the pieces of state and callbacks it needs as props. The layout and touch buttons are styled in CSS and adapt at narrower screen sizes.

## 10. Start, build, test, and troubleshoot

Use two VS Code terminals. From the project root, set up the backend once:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
cd backend
python -m uvicorn app:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Build and run backend regression tests:

```powershell
cd backend
..\.venv\Scripts\python.exe -m compileall -q app.py rooms.py tests
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Build the production frontend:

```powershell
cd frontend
npm run build
```

If the browser cannot connect, check that the backend is running, the WebSocket URL has the right host and port, and the backend allows the frontend origin. Restart Vite after editing `.env.local`. If reconnect gives an expired-token error, return home and create/join the room again. Room data is memory-only and cannot survive a backend restart.

For production, build the static frontend with `VITE_WS_BASE_URL=wss://<backend-host>`. Run Uvicorn from the `backend` directory with `--host 0.0.0.0 --port $PORT`. Configure `PIXEL_BATTLE_ALLOWED_ORIGINS` to the frontend's exact HTTPS origin. Use one persistent WebSocket-capable backend process. The game has not been publicly deployed.

## 11. One movement input from keypress to screen

Suppose the local player presses the right-arrow key:

1. The browser creates a `keydown` event.
2. `ArenaScreen.handleKeyDown()` finds `arrowright` in `keyDirections` and records `right` in its keyboard set.
3. `sendCurrentKeys()` calls the `onMovement` prop with the currently held keys.
4. `App.tsx` connected that prop to `room.sendMovement`, returned from `useRoomSocket()`.
5. `sendMovement()` sends `{"type":"input","keys":["right"]}` on the active WebSocket.
6. `room_websocket()` validates the key and calls `RoomManager.set_input()` for the correct player.
7. The next server tick in `update_loop()` calls `update_rooms()` and `update_room()`. The server attempts x and y movement separately, keeps the 32 by 32 player inside the arena, and rejects steps that overlap a solid obstacle. Coins, hazards, and danger areas are checked using their server-owned coordinates.
8. `broadcast()` sends a room snapshot to each connected player.
9. `useRoomSocket()` receives `state`, stores the new snapshot in React state, and React renders the player at the new position in `ArenaScreen` for everyone.
10. When the player releases the key, `handleKeyUp()` removes `right` and sends the remaining pressed keys (an empty list if no other key is held). The server stops horizontal movement on the next tick.

## 12. Glossary

- **Python** — the programming language used for the backend. `rooms.py` uses Python classes and functions to describe and update rooms.
- **React** — a JavaScript library for building interfaces from components. A state change in `useRoomSocket()` tells React to render the affected screen again.
- **TypeScript** — JavaScript with static types. Types such as `RoomPlayer` and `RoomSnapshot` describe the data expected by the frontend.
- **HTTP** — the request-and-response protocol used to load web pages and ordinary API responses. The backend `GET /` health check is HTTP.
- **WebSocket** — a persistent two-way connection that lets the browser send input and the server push room state in real time.
- **FastAPI** — the Python web framework that defines `app`, the health route, and `/ws/{room_code}`.
- **Uvicorn** — the ASGI server process that runs FastAPI and serves its HTTP and WebSocket connections.
- **JSON** — a text format for structured data. The game sends objects such as `{"type":"input","keys":["right"]}`.
- **React state** — component data that React watches. Updating state causes React to render the current values.
- **Environment variable** — a setting provided to a process from its shell or hosting platform, such as `PIXEL_BATTLE_MATCH_SECONDS`.
- **Git** — a version-control tool that records project changes as commits and can synchronize code with GitHub. `.gitignore` excludes local files from those commits.
- **Build** — the process that checks TypeScript and produces optimized static site files in `frontend/dist`.
- **Origin** — a browser security identity made from the URL scheme, host, and port, for example `https://pixel-battle.example.com`.
