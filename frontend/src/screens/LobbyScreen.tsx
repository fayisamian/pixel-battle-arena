import { useState } from 'react'
import type { ConnectionStatus, MapSummary, RoomPlayer } from '../types'

type LobbyScreenProps = {
  roomCode: string
  connectionStatus: ConnectionStatus
  error: string
  playerId: string
  players: RoomPlayer[]
  selectedMapId: string
  maps: MapSummary[]
  onSelectMap: (mapId: string) => void
  onStart: () => void
  onLeave: () => void
}

function connectionLabel(status: ConnectionStatus) {
  if (status === 'connected') return 'Connected to room'
  if (status === 'connecting') return 'Connecting to room…'
  if (status === 'disconnected') return 'Connection lost'
  if (status === 'error') return 'Could not join room'
  return 'Waiting to connect'
}

export function LobbyScreen({
  roomCode,
  connectionStatus,
  error,
  playerId,
  players,
  selectedMapId,
  maps,
  onSelectMap,
  onStart,
  onLeave,
}: LobbyScreenProps) {
  const [copied, setCopied] = useState(false)
  const currentPlayer = players.find((player) => player.id === playerId)
  const canStart = currentPlayer?.isHost === true && currentPlayer.isConnected
  const canChooseMap = canStart && connectionStatus === 'connected'
  const connectedCount = players.filter((player) => player.isConnected).length

  async function copyRoomCode() {
    try {
      await navigator.clipboard.writeText(roomCode)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="screen-card lobby-card" aria-labelledby="lobby-title">
      <div className="screen-heading">
        <button className="text-button" onClick={onLeave}>← Back</button>
        <span className="step-label">ROOM LOBBY</span>
      </div>
      <div className="lobby-intro">
        <p className="eyebrow">ROOM READY</p>
        <h1 id="lobby-title">Bring your <span>crew.</span></h1>
        <p>Share this code with friends so they can join the room.</p>
      </div>

      <div className="room-code-panel">
        <div><span className="field-label">ROOM CODE</span><strong className="room-code">{roomCode}</strong></div>
        <button className="button button-secondary copy-button" onClick={copyRoomCode}>
          {copied ? 'Copied!' : 'Copy code'}
        </button>
      </div>

      <div className={`connection-indicator connection-${connectionStatus}`} role="status">
        <span className="connection-dot" /> {connectionLabel(connectionStatus)}
      </div>
      {error && <p className="form-error room-error" role="alert">{error}</p>}

      <div className="map-picker" aria-labelledby="map-picker-title">
        <div className="map-picker-heading">
          <div>
            <span className="field-label" id="map-picker-title">CHOOSE THE ARENA</span>
            <p>{canChooseMap ? 'Pick a map before starting.' : 'The host chooses the map.'}</p>
          </div>
          <span className="selected-map-label">{maps.find((map) => map.id === selectedMapId)?.name ?? 'Loading map…'}</span>
        </div>
        <div className="map-options">
          {maps.map((map) => (
            <button
              className={"map-option theme-swatch-" + map.theme + (selectedMapId === map.id ? ' map-option-selected' : '')}
              key={map.id}
              type="button"
              aria-pressed={selectedMapId === map.id}
              disabled={!canChooseMap || selectedMapId === map.id}
              onClick={() => onSelectMap(map.id)}
            >
              <span className="map-option-preview" aria-hidden="true">
                <span className="preview-path" />
                <i className="preview-feature preview-feature-one" />
                <i className="preview-feature preview-feature-two" />
                <i className="preview-hazard" />
                <i className="preview-coin">¢</i>
              </span>
              <span className="map-option-copy"><strong>{map.name}</strong><small>{map.description}</small></span>
              {selectedMapId === map.id && <span className="map-selected-mark" aria-label="Selected">✓</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="lobby-section-title">
        <span>PLAYERS</span><span className="player-count">{connectedCount} online · {players.length} / 8 slots</span>
      </div>
      <div className="player-list">
        {players.map((player) => {
          const isCurrentPlayer = player.id === playerId
          return (
            <div className="player-row" key={player.id}>
              <span className="avatar" style={{ backgroundColor: `${player.color}24`, borderColor: player.color, color: player.color }}>
                {player.name.charAt(0).toUpperCase()}
              </span>
              <span className="player-detail">
                <strong>{player.name}{isCurrentPlayer ? ' (you)' : ''}</strong>
                <small>{player.isHost ? 'Room host' : 'Guest'}{player.isConnected ? '' : ' · Reconnecting'}</small>
              </span>
              <span className={`ready-tag${player.isConnected ? '' : ' ready-tag-offline'}`}>
                {player.isConnected ? 'CONNECTED' : 'OFFLINE'}
              </span>
            </div>
          )
        })}
        {players.length === 0 && connectionStatus === 'connecting' && (
          <div className="guest-waiting">Connecting to the room…</div>
        )}
      </div>
      <div className="waiting-row">
        <span className="waiting-dots">···</span>
        {players.some((player) => !player.isConnected)
          ? 'Disconnected players can rejoin for 30 seconds.'
          : players.length > 1
            ? 'Players in this room are synchronized.'
            : 'Waiting for your friends to join'}
      </div>

      <div className="lobby-actions">
        {canStart ? (
          <button className="button button-primary full-button" onClick={onStart} disabled={connectionStatus !== 'connected'}>
            Start match <span aria-hidden="true">→</span>
          </button>
        ) : (
          <div className="guest-waiting">The room host will start the match.</div>
        )}
        <button className="text-button leave-button" onClick={onLeave}>Leave room</button>
      </div>
    </section>
  )
}
