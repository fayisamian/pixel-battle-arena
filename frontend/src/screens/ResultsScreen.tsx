import type { RoomPlayer } from '../types'

type ResultsScreenProps = {
  roomCode: string
  playerId: string
  players: RoomPlayer[]
  winnerIds: string[]
  isHost: boolean
  onPlayAgain: () => void
  onLeave: () => void
}

export function ResultsScreen({
  roomCode,
  playerId,
  players,
  winnerIds,
  isHost,
  onPlayAgain,
  onLeave,
}: ResultsScreenProps) {
  const winnerNames = players
    .filter((player) => winnerIds.includes(player.id))
    .map((player) => player.id === playerId ? `${player.name} (you)` : player.name)
  const playerWon = winnerIds.includes(playerId)
  const isTie = winnerIds.length > 1

  let resultTitle = 'Match complete.'
  let resultDescription = winnerNames.length ? `${winnerNames[0]} wins the match.` : 'The match has ended.'
  if (isTie) {
    resultTitle = 'It’s a tie!'
    resultDescription = playerWon
      ? 'You share the win with the other top-scoring players.'
      : `${winnerNames.join(' and ')} share the win.`
  } else if (playerWon) {
    resultTitle = 'You win!'
    resultDescription = 'You collected the most coins.'
  }

  return (
    <section className="screen-card results-card" aria-labelledby="results-title">
      <div className="screen-heading">
        <button className="text-button" onClick={onLeave}>← Leave room</button>
        <span className="step-label">ROOM {roomCode} · MATCH OVER</span>
      </div>
      <div className="trophy" aria-hidden="true">✦</div>
      <p className="eyebrow centered">FINAL SCORES</p>
      <h1 id="results-title">{resultTitle}</h1>
      <p className="results-description">{resultDescription}</p>
      <div className="final-score-list" aria-label="Final scores">
        {[...players].sort((a, b) => b.score - a.score).map((player) => (
          <div className={`result-row${winnerIds.includes(player.id) ? ' result-row-winner' : ''}`} key={player.id}>
            <span className="avatar" style={{ backgroundColor: `${player.color}24`, borderColor: player.color, color: player.color }}>
              {player.name.charAt(0).toUpperCase()}
            </span>
            <span className="player-detail">
              <strong>{player.name}{player.id === playerId ? ' (you)' : ''}</strong>
              <small>
                {winnerIds.includes(player.id) ? 'Winner' : 'Player'}
                {!player.isConnected ? ' · Reconnect window' : ''}
              </small>
            </span>
            <strong className="result-score">{player.score}</strong>
          </div>
        ))}
      </div>
      {isHost ? (
        <button className="button button-primary full-button" onClick={onPlayAgain}>
          Play again <span aria-hidden="true">↻</span>
        </button>
      ) : (
        <div className="guest-waiting">Waiting for the host to start another match.</div>
      )}
      <button className="text-button leave-button" onClick={onLeave}>Return home</button>
    </section>
  )
}
