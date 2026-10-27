import type { CSSProperties } from 'react'
import type { ArenaArea } from '../types'
import { ARENA_HEIGHT, ARENA_WIDTH } from '../constants'

type ArenaZoneProps = {
  area: ArenaArea
  severity: 'high' | 'low'
}

export function ArenaZone({ area, severity }: ArenaZoneProps) {
  const isHighDanger = severity === 'high'
  const marker = isHighDanger ? '−10' : '−5'
  const warningSymbol = isHighDanger ? '▲' : '!'

  const position: CSSProperties = {
    left: `${(area.x / ARENA_WIDTH) * 100}%`,
    top: `${(area.y / ARENA_HEIGHT) * 100}%`,
    width: `${(area.width / ARENA_WIDTH) * 100}%`,
    height: `${(area.height / ARENA_HEIGHT) * 100}%`,
  }

  return (
    <span
      className={`arena-zone arena-zone-${severity} kind-${area.kind}`}
      data-testid={`${isHighDanger ? 'hazard' : 'danger'}-${area.id}`}
      style={position}
      aria-label={`${isHighDanger ? 'High danger hazard' : 'Penalty zone'}: ${area.kind}, ${marker} points`}
    >
      <span className="arena-zone-art" aria-hidden="true">
        <span className="arena-zone-surface" />
        <span className="arena-zone-detail" />
      </span>
      <span className={`arena-zone-marker arena-zone-marker-${severity}`} aria-hidden="true">
        <span className="arena-zone-symbol">{warningSymbol}</span>
        <strong>{marker}</strong>
      </span>
    </span>
  )
}
