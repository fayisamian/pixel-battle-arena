import { useCallback, useEffect, useRef, useState } from 'react'
import type { ArenaMap, ConnectionStatus, GameEvent, GameSpeedBoost, MapSummary, MovementKey, RoomPlayer, RoomSnapshot } from '../types'

type UseRoomSocketOptions = {
  active: boolean
  roomCode: string
  playerName: string
  isHost: boolean
}

function readResumeToken(roomCode: string) {
  try {
    return window.sessionStorage.getItem(`pixel-battle-resume:${roomCode}`)
  } catch {
    return null
  }
}

function clearResumeToken(roomCode: string) {
  try {
    window.sessionStorage.removeItem(`pixel-battle-resume:${roomCode}`)
  } catch {
    // Resume is best-effort; the player can still join with the room code.
  }
}

export function useRoomSocket({ active, roomCode, playerName, isHost }: UseRoomSocketOptions) {
  const socketRef = useRef<WebSocket | null>(null)
  const intentionallyLeavingRef = useRef(false)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('idle')
  const [playerId, setPlayerId] = useState('')
  const [roomState, setRoomState] = useState<RoomSnapshot | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!active || !roomCode) {
      setConnectionStatus('idle')
      setPlayerId('')
      setRoomState(null)
      setError('')
      return
    }

    let socket: WebSocket | null = null
    let isLeaving = false
    let receivedServerError = false
    let reconnectTimer = 0
    intentionallyLeavingRef.current = false

    setConnectionStatus('connecting')
    if (reconnectAttempt === 0) {
      setPlayerId('')
      setRoomState(null)
    }
    setError('')

    // The short delay lets React StrictMode cancel its development-only test
    // effect before it creates a real room connection.
    const connectTimer = window.setTimeout(() => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const defaultBase = `${protocol}//${window.location.hostname}:8000`
      const baseUrl = (import.meta.env.VITE_WS_BASE_URL || defaultBase).replace(/\/$/, '')
      socket = new WebSocket(`${baseUrl}/ws/${encodeURIComponent(roomCode)}`)
      socketRef.current = socket

      socket.onopen = () => {
        const resumeToken = readResumeToken(roomCode)
        socket?.send(JSON.stringify({
          type: 'join',
          name: playerName,
          isHost,
          ...(resumeToken ? { resumeToken } : {}),
        }))
      }

      socket.onmessage = (event) => {
        if (isLeaving) return

        try {
          const message = JSON.parse(event.data)
          if (message.type === 'joined') {
            setPlayerId(message.playerId)
            if (typeof message.resumeToken === 'string') {
              try {
                window.sessionStorage.setItem(`pixel-battle-resume:${roomCode}`, message.resumeToken)
              } catch {
                // Reconnection still works while the socket remains open.
              }
            }
          } else if (message.type === 'state') {
            setRoomState({
              roomCode: message.roomCode,
              status: message.status,
              players: Array.isArray(message.players)
                ? message.players.map((player: RoomPlayer) => ({
                    ...player,
                    speedBoostRemaining: Number.isFinite(player.speedBoostRemaining)
                      ? Math.max(0, player.speedBoostRemaining)
                      : 0,
                  }))
                : [],
              coins: message.coins ?? [],
              speedBoost: (
                message.speedBoost
                && typeof message.speedBoost.id === 'string'
                && Number.isFinite(message.speedBoost.x)
                && Number.isFinite(message.speedBoost.y)
              )
                ? message.speedBoost as GameSpeedBoost
                : null,
              timeRemaining: message.timeRemaining ?? 0,
              winnerIds: message.winnerIds ?? [],
              map: message.map as ArenaMap,
              availableMaps: message.availableMaps ?? [],
              events: message.events ?? [],
            })
            setConnectionStatus('connected')
          } else if (message.type === 'error') {
            receivedServerError = true
            setError(message.message)
            setConnectionStatus('error')
          }
        } catch {
          setError('The server sent a message the browser could not read.')
          setConnectionStatus('error')
        }
      }

      socket.onerror = () => {
        if (!isLeaving) {
          setError('Connection interrupted. Trying to reconnect…')
          setConnectionStatus('disconnected')
        }
      }

      socket.onclose = (event) => {
        if (isLeaving || intentionallyLeavingRef.current || receivedServerError) return
        if (event.code === 4001) {
          setError('This room session is active in another tab.')
          setConnectionStatus('error')
          return
        }
        if (!isLeaving && !receivedServerError) {
          setError('Connection interrupted. Trying to reconnect…')
          setConnectionStatus('disconnected')
          const delay = Math.min(1000 * (2 ** Math.min(reconnectAttempt, 2)), 5000)
          reconnectTimer = window.setTimeout(() => {
            setReconnectAttempt((attempt) => attempt + 1)
          }, delay)
        }
      }
    }, 0)

    return () => {
      isLeaving = true
      window.clearTimeout(connectTimer)
      window.clearTimeout(reconnectTimer)
      if (socketRef.current === socket) {
        socketRef.current = null
      }
      socket?.close()
    }
  }, [active, isHost, playerName, reconnectAttempt, roomCode])

  const selectMap = useCallback((mapId: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'select_map', mapId }))
    }
  }, [])

  const startMatch = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'start_match' }))
    }
  }, [])

  const sendMovement = useCallback((keys: MovementKey[]) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'input', keys }))
    }
  }, [])

  const leaveRoom = useCallback(() => {
    intentionallyLeavingRef.current = true
    clearResumeToken(roomCode)
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: 'leave' }))
    }
  }, [roomCode])

  return {
    connectionStatus,
    error,
    playerId,
    players: roomState?.players ?? [],
    coins: roomState?.coins ?? [],
    speedBoost: roomState?.speedBoost ?? null,
    map: roomState?.map ?? null,
    availableMaps: (roomState?.availableMaps ?? []) as MapSummary[],
    events: (roomState?.events ?? []) as GameEvent[],
    timeRemaining: roomState?.timeRemaining ?? 0,
    winnerIds: roomState?.winnerIds ?? [],
    roomStatus: roomState?.status ?? 'lobby',
    sendMovement,
    selectMap,
    startMatch,
    leaveRoom,
  }
}
