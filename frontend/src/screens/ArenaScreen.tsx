import { useEffect, useRef, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'
import type { ArenaMap, ConnectionStatus, GameCoin, GameEvent, GameSpeedBoost, MovementKey, RoomPlayer } from '../types'
import { ArenaZone } from '../components/ArenaZone'
import './ArenaVisuals.css'
import { ARENA_HEIGHT, ARENA_WIDTH } from '../constants'

const keyDirections: Record<string, MovementKey> = {
  w: 'up',
  arrowup: 'up',
  s: 'down',
  arrowdown: 'down',
  a: 'left',
  arrowleft: 'left',
  d: 'right',
  arrowright: 'right',
}

type ArenaScreenProps = {
  playerName: string
  roomCode: string
  connectionStatus: ConnectionStatus
  error: string
  playerId: string
  players: RoomPlayer[]
  coins: GameCoin[]
  speedBoost: GameSpeedBoost | null
  map: ArenaMap | null
  events: GameEvent[]
  timeRemaining: number
  onMovement: (keys: MovementKey[]) => void
  onLeave: () => void
}

const directions: { key: MovementKey; label: string }[] = [
  { key: 'up', label: 'Move up' },
  { key: 'left', label: 'Move left' },
  { key: 'down', label: 'Move down' },
  { key: 'right', label: 'Move right' },
]

function getPlayerLabelOffset(player: RoomPlayer, players: RoomPlayer[]) {
  const playerIndex = players.findIndex((candidate) => candidate.id === player.id)
  const nearbyPlayersBeforeThisOne = players
    .slice(0, playerIndex)
    .filter((other) => Math.abs(other.x - player.x) < 96 && Math.abs(other.y - player.y) < 58)

  // A separate 22px row keeps this name tag readable when player sprites overlap.
  return nearbyPlayersBeforeThisOne.length * 22
}

export function ArenaScreen({
  playerName,
  roomCode,
  connectionStatus,
  error,
  playerId,
  players,
  coins,
  speedBoost,
  map,
  events,
  timeRemaining,
  onMovement,
  onLeave,
}: ArenaScreenProps) {
  const keyboardKeys = useRef(new Set<MovementKey>())
  const touchKeys = useRef(new Set<MovementKey>())

  useEffect(() => {
    function sendCurrentKeys() {
      onMovement([...new Set([...keyboardKeys.current, ...touchKeys.current])])
    }

    function handleKeyDown(event: KeyboardEvent) {
      const direction = keyDirections[event.key.toLowerCase()]
      if (!direction) return
      event.preventDefault()
      if (!keyboardKeys.current.has(direction)) {
        keyboardKeys.current.add(direction)
        sendCurrentKeys()
      }
    }

    function handleKeyUp(event: KeyboardEvent) {
      const direction = keyDirections[event.key.toLowerCase()]
      if (!direction) return
      event.preventDefault()
      if (keyboardKeys.current.delete(direction)) sendCurrentKeys()
    }

    function handleBlur() {
      keyboardKeys.current.clear()
      touchKeys.current.clear()
      sendCurrentKeys()
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('blur', handleBlur)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('blur', handleBlur)
      keyboardKeys.current.clear()
      touchKeys.current.clear()
      onMovement([])
    }
  }, [onMovement])

  function setTouchDirection(direction: MovementKey, pressed: boolean) {
    const changed = pressed
      ? !touchKeys.current.has(direction)
      : touchKeys.current.has(direction)

    if (!changed) return
    if (pressed) touchKeys.current.add(direction)
    else touchKeys.current.delete(direction)
    onMovement([...new Set([...keyboardKeys.current, ...touchKeys.current])])
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLButtonElement>, direction: MovementKey) {
    event.currentTarget.setPointerCapture(event.pointerId)
    setTouchDirection(direction, true)
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLButtonElement>, direction: MovementKey) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    setTouchDirection(direction, false)
  }

  function handleControlKey(event: ReactKeyboardEvent<HTMLButtonElement>, direction: MovementKey) {
    if (event.key !== ' ' && event.key !== 'Enter') return
    event.preventDefault()
    if (event.type === 'keydown') {
      if (!event.repeat) setTouchDirection(direction, true)
    } else {
      setTouchDirection(direction, false)
    }
  }

  return (
    <section className="screen-card arena-card" aria-labelledby="arena-title">
      <div className="screen-heading">
        <button className="text-button" onClick={onLeave}>← Leave room</button>
        <span className="step-label">ROOM {roomCode}</span>
      </div>
      <div className="match-heading">
        <div><p className="eyebrow">LIVE ROOM</p><h1 id="arena-title">Collect <span>coins.</span></h1></div>
        <div className="timer-box" aria-label={`Time remaining: ${timeRemaining} seconds`}>
          <small>TIME LEFT</small><strong data-testid="match-timer">{Math.floor(timeRemaining / 60)}:{String(timeRemaining % 60).padStart(2, '0')}</strong>
        </div>
        <div className={`connection-indicator connection-${connectionStatus}`} role="status">
          <span className="connection-dot" />
          {connectionStatus === 'connected' ? 'Live' : connectionStatus === 'connecting' ? 'Connecting' : 'Connection lost'}
        </div>
      </div>

      {error && <p className="form-error room-error" role="alert">{error}</p>}
      <div
        className="game-board live-game-board"
        data-theme={map?.theme ?? "grasslands"}
        style={map ? {
          "--arena-ground": map.ground,
          "--arena-wall": map.wall,
          "--arena-wall-highlight": map.wallHighlight,
        } as CSSProperties : undefined}
        aria-label={"Live multiplayer arena: " + (map?.name ?? "loading map")}
      >
        {map?.dangerZones.map((area) => (
          <ArenaZone key={area.id} area={area} severity="low" />
        ))}
        {map?.hazards.map((area) => (
          <ArenaZone key={area.id} area={area} severity="high" />
        ))}
        {map?.obstacles.map((area) => (
          <span
            className={"arena-obstacle kind-" + area.kind}
            key={area.id}
            data-testid={"obstacle-" + area.id}
            style={{ left: (area.x / ARENA_WIDTH) * 100 + "%", top: (area.y / ARENA_HEIGHT) * 100 + "%", width: (area.width / ARENA_WIDTH) * 100 + "%", height: (area.height / ARENA_HEIGHT) * 100 + "%" }}
            aria-label={"Solid obstacle: " + area.kind}
          />
        ))}
        {coins.map((coin) => (
          <span
            className={`pixel-coin live-coin theme-coin-${map?.theme ?? 'grasslands'}`}
            key={coin.id}
            data-testid="game-coin"
            aria-label="Coin"
            style={{ left: (coin.x / ARENA_WIDTH) * 100 + "%", top: (coin.y / ARENA_HEIGHT) * 100 + "%" }}
          >¢</span>
        ))}
        {speedBoost && (
          <span
            className="speed-boost-pickup"
            data-theme={map?.theme ?? 'grasslands'}
            data-testid="speed-boost-pickup"
            style={{
              left: (speedBoost.x / ARENA_WIDTH) * 100 + "%",
              top: (speedBoost.y / ARENA_HEIGHT) * 100 + "%",
            }}
            aria-label="Speed boost power-up"
            title="Speed boost"
          >
            <span className="speed-boost-bolt" aria-hidden="true">⚡</span>
          </span>
        )}
        {players.map((player) => (
          <div
            className={"pixel-player live-player" + (player.id === playerId ? " player-self" : "") + (player.isConnected ? "" : " player-disconnected") + (player.speedBoostRemaining > 0 ? " player-boosted" : "")}
            key={player.id}
            style={{
              left: (player.x / ARENA_WIDTH) * 100 + "%",
              top: (player.y / ARENA_HEIGHT) * 100 + "%",
              backgroundColor: player.color,
              borderColor: player.id === playerId ? "#e2fff3" : "#fff1df",
            }}
            aria-label={player.name + (player.id === playerId ? ", you" : "") + (player.isConnected ? "" : ", reconnecting") + (player.speedBoostRemaining > 0 ? ", speed boost active" : "")}
          >
            <span
              className="live-player-name"
              style={{
                left: player.x >= ARENA_WIDTH / 2 ? "auto" : 0,
                right: player.x >= ARENA_WIDTH / 2 ? 0 : "auto",
                top: player.y < ARENA_HEIGHT * 0.35
                  ? `calc(100% + 5px + ${getPlayerLabelOffset(player, players)}px)`
                  : "auto",
                bottom: player.y < ARENA_HEIGHT * 0.35
                  ? "auto"
                  : `calc(100% + 5px + ${getPlayerLabelOffset(player, players)}px)`,
              }}
            >{player.name}{player.id === playerId ? " · YOU" : ""}</span>
            <i />
          </div>
        ))}
        {events.map((event) => (
          <span
            className={"score-feedback " + (event.points > 0 ? "score-feedback-positive" : "score-feedback-negative")}
            key={event.id}
            data-testid="score-feedback"
            style={{ left: (event.x / ARENA_WIDTH) * 100 + "%", top: (event.y / ARENA_HEIGHT) * 100 + "%" }}
            aria-label={(event.points > 0 ? "Collected coin: " : "Penalty: ") + Math.abs(event.points) + " points"}
          >{event.points > 0 ? "+" : ""}{event.points}</span>
        ))}
        <div className="board-hud"><span>{map?.name ?? "PIXEL ARENA"}</span><span>{players.length} PLAYER{players.length === 1 ? '' : 'S'} · {coins.length} COINS</span></div>
      </div>

      <div className="scoreboard" aria-label="Live scores">
        {players.map((player) => (
          <div className="score-chip" key={player.id}>
            <span className="score-swatch" style={{ backgroundColor: player.color }} />
            <span>{player.name}{player.id === playerId ? ' (you)' : ''}{player.isConnected ? '' : ' · reconnecting'}</span>
            {player.isHost && <small className="host-badge">HOST</small>}
            {player.speedBoostRemaining > 0 && (
              <small
                className="boost-status"
                data-testid="boost-status"
                aria-label={player.name + ' speed boost, ' + player.speedBoostRemaining.toFixed(1) + ' seconds remaining'}
                title="Remaining time is synchronized from the server"
              >
                <span aria-hidden="true">⚡</span>
                {player.speedBoostRemaining.toFixed(1)}s
              </small>
            )}
            <strong data-testid={`score-${player.id}`}>{player.score}</strong>
          </div>
        ))}
      </div>

      <div className="arena-controls-row">
        <div className="player-chip"><span className="avatar avatar-mint">{playerName.charAt(0).toUpperCase()}</span><span>{playerName || 'Pixel Player'}</span></div>
        <div className="keyboard-hint"><span>MOVE</span><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd><span className="or-label">or arrows</span></div>
        <div className="touch-controls" aria-label="Touch movement controls">
          {directions.map(({ key, label }) => (
            <button
              className={`touch-button touch-${key}`}
              key={key}
              type="button"
              aria-label={label}
              onPointerDown={(event) => handlePointerDown(event, key)}
              onPointerUp={(event) => handlePointerUp(event, key)}
              onPointerCancel={(event) => handlePointerUp(event, key)}
              onKeyDown={(event) => handleControlKey(event, key)}
              onKeyUp={(event) => handleControlKey(event, key)}
            >
              {key === 'up' ? '↑' : key === 'down' ? '↓' : key === 'left' ? '←' : '→'}
            </button>
          ))}
        </div>
      </div>
      <p className="movement-note">Coins add 10 points. Hazards remove 10 and danger zones remove 5. Movement and scores are controlled by the server.</p>
    </section>
  )
}
