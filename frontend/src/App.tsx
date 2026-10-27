import { useEffect, useState } from 'react'
import './App.css'
import { ArenaScreen } from './screens/ArenaScreen'
import { HomeScreen } from './screens/HomeScreen'
import { LobbyScreen } from './screens/LobbyScreen'
import { ResultsScreen } from './screens/ResultsScreen'
import { useRoomSocket } from './hooks/useRoomSocket'

type Screen = 'home' | 'lobby' | 'arena' | 'results'
type SavedRoomSession = { roomCode: string; playerName: string; isHost: boolean }

const ROOM_SESSION_KEY = 'pixel-battle-room-session'

function readSavedRoomSession(): SavedRoomSession | null {
  try {
    const saved = window.sessionStorage.getItem(ROOM_SESSION_KEY)
    if (!saved) return null
    const session = JSON.parse(saved)
    if (
      typeof session.roomCode === 'string'
      && /^[A-Z0-9]{6}$/.test(session.roomCode)
      && typeof session.playerName === 'string'
      && typeof session.isHost === 'boolean'
    ) {
      return session
    }
  } catch {
    // A malformed or unavailable session should take the player to the home screen.
  }
  return null
}

function saveRoomSession(session: SavedRoomSession) {
  try {
    window.sessionStorage.setItem(ROOM_SESSION_KEY, JSON.stringify(session))
  } catch {
    // Multiplayer still works when browser storage is unavailable; refresh recovery is optional.
  }
}

function clearRoomSession() {
  try {
    window.sessionStorage.removeItem(ROOM_SESSION_KEY)
  } catch {
    // Clearing saved reconnect details is optional when browser storage is unavailable.
  }
}

const roomCharacters = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

function createRoomCode() {
  return Array.from({ length: 6 }, () =>
    roomCharacters[Math.floor(Math.random() * roomCharacters.length)],
  ).join('')
}

function App() {
  const [savedRoomSession] = useState(readSavedRoomSession)
  const [screen, setScreen] = useState<Screen>(() => savedRoomSession ? 'lobby' : 'home')
  const [playerName, setPlayerName] = useState(savedRoomSession?.playerName ?? '')
  const [roomCode, setRoomCode] = useState(savedRoomSession?.roomCode ?? '')
  const [isHost, setIsHost] = useState(savedRoomSession?.isHost ?? false)
  const room = useRoomSocket({
    active: screen === 'lobby' || screen === 'arena' || screen === 'results',
    roomCode,
    playerName,
    isHost,
  })

  useEffect(() => {
    if ((screen === 'lobby' || screen === 'results') && room.roomStatus === 'playing') {
      setScreen('arena')
    } else if ((screen === 'arena' || screen === 'lobby') && room.roomStatus === 'finished') {
      setScreen('results')
    }
  }, [room.roomStatus, screen])

  function handleCreateRoom(name: string) {
    const normalizedName = name.trim() || 'Pixel Player'
    const newRoomCode = createRoomCode()
    setPlayerName(normalizedName)
    setRoomCode(newRoomCode)
    setIsHost(true)
    saveRoomSession({ roomCode: newRoomCode, playerName: normalizedName, isHost: true })
    setScreen('lobby')
  }

  function handleJoinRoom(name: string, code: string) {
    const normalizedCode = code.trim().toUpperCase()
    if (!/^[A-Z0-9]{6}$/.test(normalizedCode)) {
      return 'Enter a six-character room code.'
    }

    const normalizedName = name.trim() || 'Pixel Player'
    setPlayerName(normalizedName)
    setRoomCode(normalizedCode)
    setIsHost(false)
    saveRoomSession({ roomCode: normalizedCode, playerName: normalizedName, isHost: false })
    setScreen('lobby')
    return ''
  }

  function returnHome() {
    room.leaveRoom()
    clearRoomSession()
    setScreen('home')
    setRoomCode('')
    setIsHost(false)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#home" onClick={(event) => { event.preventDefault(); returnHome() }}>
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>Pixel Battle <strong>Arena</strong></span>
        </a>
        <span className="phase-badge"><span /> REAL-TIME PLAY</span>
      </header>

      <main className="page-content">
        {screen === 'home' && (
          <HomeScreen
            onCreateRoom={handleCreateRoom}
            onJoinRoom={handleJoinRoom}
          />
        )}
        {screen === 'lobby' && (
          <LobbyScreen
            roomCode={roomCode}
            connectionStatus={room.connectionStatus}
            error={room.error}
            playerId={room.playerId}
            players={room.players}
            selectedMapId={room.map?.id ?? "grasslands"}
            maps={room.availableMaps}
            onSelectMap={room.selectMap}
            onStart={room.startMatch}
            onLeave={returnHome}
          />
        )}
        {screen === 'arena' && (
          <ArenaScreen
            playerName={playerName}
            roomCode={roomCode}
            connectionStatus={room.connectionStatus}
            error={room.error}
            playerId={room.playerId}
            players={room.players}
            coins={room.coins}
            speedBoost={room.speedBoost}
            map={room.map}
            events={room.events}
            timeRemaining={room.timeRemaining}
            onMovement={room.sendMovement}
            onLeave={returnHome}
          />
        )}
        {screen === 'results' && (
          <ResultsScreen
            roomCode={roomCode}
            playerId={room.playerId}
            players={room.players}
            winnerIds={room.winnerIds}
            isHost={room.players.some((player) => player.id === room.playerId && player.isHost && player.isConnected)}
            onPlayAgain={room.startMatch}
            onLeave={returnHome}
          />
        )}
      </main>

      <footer className="site-footer">
        <span>NO ACCOUNTS · JUST PIXELS</span>
        <span>MAPS · COLLISIONS · GAMEPLAY</span>
      </footer>
    </div>
  )
}

export default App