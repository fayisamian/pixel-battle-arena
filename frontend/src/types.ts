export type MovementKey = 'up' | 'down' | 'left' | 'right'

export type RoomPlayer = {
  id: string
  name: string
  x: number
  y: number
  color: string
  isHost: boolean
  isConnected: boolean
  score: number
  speedBoostRemaining: number
}

export type GameCoin = { id: string; x: number; y: number }
export type GameSpeedBoost = { id: string; x: number; y: number }
export type ArenaArea = { id: string; x: number; y: number; width: number; height: number; kind: string }
export type MapSummary = { id: string; name: string; description: string; theme: string }
export type ArenaMap = MapSummary & {
  width: number
  height: number
  ground: string
  grid: string
  wall: string
  wallHighlight: string
  hazardColor: string
  dangerColor: string
  obstacles: ArenaArea[]
  hazards: ArenaArea[]
  dangerZones: ArenaArea[]
  coinSpawns: { x: number; y: number }[]
  playerSpawns: { x: number; y: number }[]
}
export type GameEvent = {
  id: string
  playerId: string
  kind: 'coin' | 'penalty'
  points: number
  x: number
  y: number
  expiresAt: number
}

export type RoomSnapshot = {
  roomCode: string
  status: 'lobby' | 'playing' | 'finished'
  players: RoomPlayer[]
  coins: GameCoin[]
  speedBoost: GameSpeedBoost | null
  timeRemaining: number
  winnerIds: string[]
  map: ArenaMap
  availableMaps: MapSummary[]
  events: GameEvent[]
}

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'error'
  | 'disconnected'