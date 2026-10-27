# Pixel Battle Arena

A small browser multiplayer game. The frontend is React, TypeScript, and Vite. The backend is Python, FastAPI, and WebSockets. Rooms and matches live in backend memory, so run exactly one backend process and expect all rooms to disappear when that process restarts.

## Prerequisites

- Python 3.11 or newer
- Node.js and npm
- VS Code (recommended, not required)

## Run locally in VS Code

Open this project folder in VS Code. Use two terminals so the backend and frontend keep running at the same time.

### Backend terminal

From the project root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
cd backend
python -m uvicorn app:app --reload
```

If PowerShell blocks activation, either allow the script in your current user session or run the virtual-environment Python directly:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

The backend health check is at <http://127.0.0.1:8000/>. Keep this terminal open.

Optional local settings can be copied from `backend/.env.example` into the terminal. PowerShell example for a shorter match:

```powershell
$env:PIXEL_BATTLE_MATCH_SECONDS = "10"
python -m uvicorn app:app --reload
```

The Python application does not load `.env` files automatically. Set these values in the shell or your hosting provider's environment settings.

### Frontend terminal

Open a second terminal at the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local Vite address, usually <http://localhost:5173/>. The frontend connects to `ws://<current-hostname>:8000` by default. To change it, copy `frontend/.env.example` to `frontend/.env.local`, edit `VITE_WS_BASE_URL`, then restart Vite. For example:

```dotenv
VITE_WS_BASE_URL=ws://127.0.0.1:8010
```

For two devices on the same Wi-Fi, the backend must listen on the network interface and the firewall must permit its port. Open Vite using the development computer's LAN address; configure the matching WebSocket address in `VITE_WS_BASE_URL`. Also set `PIXEL_BATTLE_ALLOWED_ORIGINS` to the exact frontend origin, such as `http://192.168.1.20:5173`, before starting the backend.

## Play and verify manually

1. Open the app in two browser tabs.
2. Create a room in one tab and join its six-character code in the other.
3. In the lobby, have the host choose Grasslands Arena, Desert Ruins, Neon Cyber Arena, or Frozen Labyrinth. Confirm the other tab shows the same selection.
4. Start the match. Move with WASD, arrow keys, or touch controls. Walls stop movement, coins add 10 points, hazards remove 10, and danger zones remove 5. Scores stop at zero.
5. Refresh a tab during the match. Within 30 seconds it should reconnect as the same player with the same position and score.
6. Close the host tab without choosing Leave Room. The other player should become host; the arena scoreboard displays the host badge, and the host can restart at the results screen.
7. Test a made-up room code, eight players and a ninth player, two separate rooms, and touch controls at a narrow browser width.
8. Choose **Leave room** to remove a player immediately. Closing a tab without leaving reserves the player for 30 seconds.

## Automated checks

Backend tests use Python's built-in `unittest`, so no test package is needed:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -m compileall -q app.py rooms.py maps.py tests
```

For an actual two-client WebSocket check, start the backend in another terminal with a short timer, then run the smoke script:

```powershell
$env:PIXEL_BATTLE_MATCH_SECONDS = "5"
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

In a second backend terminal:

```powershell
..\.venv\Scripts\python.exe tests\websocket_smoke.py
```

It exercises two connected WebSocket clients, synchronized map selection, movement, 10-point coin scoring, reconnect, host transfer, match completion/restart, invalid codes, room capacity, and room isolation. Set `WS_BASE_URL` if the backend uses another URL.

Frontend type-check and production bundle:

```powershell
cd frontend
npm run build
```

The backend tests exercise room rules and WebSocket-backed room-manager behavior with fake sockets. A browser-based two-window and touch-control check is still useful after code changes.

## Configuration

| Setting | Where | Purpose |
| --- | --- | --- |
| `VITE_WS_BASE_URL` | Frontend build environment | WebSocket base URL, e.g. `ws://localhost:8000` locally or `wss://api.example.com` in production. Vite embeds this at build time. |
| `PIXEL_BATTLE_MATCH_SECONDS` | Backend runtime environment | Match length in seconds. Defaults to `120`. |
| `PIXEL_BATTLE_ALLOWED_ORIGINS` | Backend runtime environment | Comma-separated browser origins permitted to open WebSockets. Defaults to the two local Vite origins. |
| `PORT` | Hosting provider | HTTP/WebSocket port for the production Uvicorn service. |

The backend checks the browser's `Origin` header against `PIXEL_BATTLE_ALLOWED_ORIGINS`. For production, set this to the exact frontend origin, including scheme and any custom port, for example `https://pixel-battle.example.com`. WebSocket URLs use `wss://` when the frontend is served over HTTPS. The app currently makes no cross-origin HTTP API calls, so FastAPI HTTP CORS middleware is not needed for the current frontend. If HTTP API calls are added later, configure CORS for their frontend origin too.

## Build and run as a production process

Build the frontend:

```powershell
cd frontend
npm ci
npm run build
```

Serve `frontend/dist` from a static hosting service. Build-time `VITE_WS_BASE_URL` must contain the public backend's `wss://` URL before `npm run build` runs.

From the backend service's working directory, install and run:

```sh
python -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port "$PORT"
```

Use a hosting service that supports persistent WebSocket connections. Run one backend process/worker only: room state is in memory and multiple workers would each have separate rooms. Restarting or sleeping the process ends all active rooms and matches. No database is required for this prototype.

### Beginner-friendly hosting suggestion

One simple split deployment is a static frontend plus a Python web service. For example, Render supports static sites and WebSocket-capable web services; set the backend root directory to `backend`, build command to `pip install -r requirements.txt`, and start command to `uvicorn app:app --host 0.0.0.0 --port $PORT`. Set `PIXEL_BATTLE_ALLOWED_ORIGINS` on the backend to the static site's exact origin. Set `VITE_WS_BASE_URL` on the frontend build service to the backend URL using `wss://`, then trigger a frontend rebuild. Read the provider's current limits before inviting players: free web services can sleep when idle, which stops in-memory rooms. See [Render's FastAPI deployment guide](https://render.com/docs/deploy-fastapi), [Web Services documentation](https://render.com/docs/web-services), and [environment-variable guide](https://render.com/docs/configure-environment-variables).

This repository is prepared for deployment, but the game has **not** been deployed to a public URL.

## Troubleshooting

- **Room connection error:** make sure the backend terminal is still running and that `VITE_WS_BASE_URL` points to its host and port. Restart Vite after changing the setting.
- **Browser blocks an origin:** add the exact frontend origin to `PIXEL_BATTLE_ALLOWED_ORIGINS` and restart the backend.
- **Refresh recovery fails:** use the same browser tab and room during the 30-second grace period. Session storage is scoped to that tab. A stale or expired token now produces a clear error; return home and join/create again.
- **Room disappeared:** the backend process restarted, slept, or all players' reconnect windows expired. Rooms are intentionally held only in memory.
- **A device on Wi-Fi cannot connect:** bind Uvicorn to `0.0.0.0`, allow the backend port through the host firewall, and configure the frontend WebSocket URL to use the computer's LAN address.
- **Port 8000 is busy:** start the backend on another port and set the matching `VITE_WS_BASE_URL` before starting Vite.

See [LEARNING_GUIDE.md](LEARNING_GUIDE.md) for a walkthrough of the code and [FILE_CHANGELOG.md](FILE_CHANGELOG.md) for this completion pass's file list.
