import { useState } from 'react'

type HomeScreenProps = {
  onCreateRoom: (name: string) => void
  onJoinRoom: (name: string, code: string) => string
}

export function HomeScreen({ onCreateRoom, onJoinRoom }: HomeScreenProps) {
  const [name, setName] = useState('')
  const [roomCode, setRoomCode] = useState('')
  const [error, setError] = useState('')

  function handleJoin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(onJoinRoom(name, roomCode))
  }

  return (
    <section className="home-layout" aria-labelledby="welcome-title">
      <div className="welcome-copy">
        <p className="eyebrow"><span className="eyebrow-square" /> QUICK MATCH · NO LOGIN</p>
        <h1 id="welcome-title">Small arena.<br /><span>Big energy.</span></h1>
        <p className="welcome-description">
          Create a room, invite your friends with a code, and move around the
          same little pixel arena in real time.
        </p>

        <label className="field-label" htmlFor="player-name">YOUR PLAYER NAME</label>
        <input
          id="player-name"
          className="text-input name-input"
          maxLength={16}
          placeholder="e.g. PixelFox"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />

        <div className="action-grid">
          <button className="button button-primary" onClick={() => onCreateRoom(name)}>
            <span aria-hidden="true">＋</span> Create a room
          </button>
          <form className="join-form" onSubmit={handleJoin}>
            <label className="field-label" htmlFor="room-code">HAVE A ROOM CODE?</label>
            <div className="join-row">
              <input
                id="room-code"
                className="text-input code-input"
                maxLength={6}
                placeholder="ABC123"
                value={roomCode}
                onChange={(event) => setRoomCode(event.target.value.toUpperCase())}
                aria-describedby={error ? 'join-error' : undefined}
              />
              <button className="button button-secondary" type="submit">Join <span aria-hidden="true">→</span></button>
            </div>
            {error && <p className="form-error" id="join-error" role="alert">{error}</p>}
          </form>
        </div>

        <p className="microcopy">No sign-up. No downloads. Just pick a name and play.</p>
      </div>

      <div className="preview-wrap" aria-label="Pixel arena preview">
        <div className="preview-label"><span className="live-dot" /> ARENA PREVIEW</div>
        <div className="preview-board">
          <span className="pixel-player player-one"><i /></span>
          <span className="pixel-player player-two"><i /></span>
          <span className="pixel-player player-three"><i /></span>
          <span className="board-bush bush-one" />
          <span className="board-bush bush-two" />
          <span className="board-stone stone-one" />
          <span className="board-stone stone-two" />
          <div className="board-hud"><span>ROOM PREVIEW</span><span>LIVE</span></div>
        </div>
        <div className="preview-caption"><span>✦</span> A little chaos goes a long way.</div>
      </div>
    </section>
  )
}
