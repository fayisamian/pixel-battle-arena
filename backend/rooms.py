import asyncio
import logging
import math
import os
import random
import time
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket

from maps import MAPS, get_map, map_summaries, rectangles_overlap, valid_spawn

ARENA_WIDTH = 960
ARENA_HEIGHT = 540
PLAYER_SIZE = 32
PLAYER_SPEED = 220
SPEED_BOOST_MULTIPLIER = 1.5
SPEED_BOOST_DURATION_SECONDS = 5.0
UPDATE_SECONDS = 1 / 20
MAX_PLAYERS = 8
COIN_COUNT = 8
COIN_RADIUS = 12
MATCH_DURATION_SECONDS = int(os.environ.get("PIXEL_BATTLE_MATCH_SECONDS", "120"))
RECONNECT_GRACE_SECONDS = 30
logger = logging.getLogger(__name__)

PLAYER_COLORS = [
    "#61d4ad",
    "#ff9a64",
    "#a996f5",
    "#65b9f2",
    "#f278a8",
    "#e1bd58",
    "#78cf67",
    "#ef825d",
]


@dataclass
class Player:
    player_id: str
    name: str
    websocket: WebSocket | None
    x: float
    y: float
    color: str
    is_host: bool
    score: int = 0
    resume_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    disconnected_at: float | None = None
    keys: set[str] = field(default_factory=set)
    pending_keys: set[str] = field(default_factory=set)
    penalty_cooldowns: dict[str, float] = field(default_factory=dict)
    active_penalties: set[str] = field(default_factory=set)
    speed_boost_until: float | None = None


@dataclass
class Coin:
    coin_id: str
    x: float
    y: float


@dataclass
class SpeedBoost:
    powerup_id: str
    x: float
    y: float


@dataclass
class Room:
    code: str
    players: dict[str, Player] = field(default_factory=dict)
    status: str = "lobby"
    coins: list[Coin] = field(default_factory=list)
    speed_boost: SpeedBoost | None = None
    map_id: str = "grasslands"
    events: list[dict] = field(default_factory=list)
    match_ends_at: float | None = None
    broadcast_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RoomManager:
    """Keeps the active rooms and their players in memory."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    async def add_player(
        self,
        room_code: str,
        name: str,
        is_host: bool,
        websocket: WebSocket,
        resume_token: str | None = None,
    ) -> tuple[Player | None, str | None]:
        room = self.rooms.get(room_code)

        if resume_token is not None:
            if room is None:
                return None, "The reconnect window has expired or this room has closed. Return home to join again."

            returning_player = next(
                (player for player in room.players.values() if player.resume_token == resume_token),
                None,
            )
            if returning_player is None:
                return None, "This reconnect token no longer belongs to a player in this room. Return home to join again."

            still_in_grace = (
                returning_player.disconnected_at is None
                or time.monotonic() - returning_player.disconnected_at < RECONNECT_GRACE_SECONDS
            )
            if still_in_grace:
                old_websocket = returning_player.websocket
                returning_player.websocket = websocket
                returning_player.disconnected_at = None
                returning_player.keys.clear()
                returning_player.pending_keys.clear()
                if not any(
                    player.is_host and player.websocket is not None
                    for player in room.players.values()
                ):
                    for player in room.players.values():
                        if player.is_host:
                            player.is_host = False
                    returning_player.is_host = True
                if old_websocket is not None:
                    try:
                        await old_websocket.close(code=4001, reason="Room session resumed")
                    except Exception:
                        pass
                return returning_player, None

            self._remove_player(room, returning_player.player_id)
            if not any(player.is_host and player.websocket is not None for player in room.players.values()):
                next_host = next(
                    (player for player in room.players.values() if player.websocket is not None),
                    None,
                )
                if next_host is not None:
                    next_host.is_host = True
            if not room.players:
                self.rooms.pop(room.code, None)
            else:
                await self.broadcast(room)
            return None, "The 30-second reconnect window has expired. Return home to join again."

        if is_host:
            if room is not None:
                return None, "That room code is already in use. Create another room."
            room = Room(code=room_code)
            self.rooms[room_code] = room
        elif room is None:
            return None, "Room not found. Check the code and try again."

        if len(room.players) >= MAX_PLAYERS:
            return None, "This room is full."
        if room.status != "lobby":
            return None, "This match has already started."

        spawn_index = len(room.players)
        connected_host_exists = any(
            other.is_host and other.websocket is not None for other in room.players.values()
        )
        if not is_host and not connected_host_exists:
            for other in room.players.values():
                if other.is_host:
                    other.is_host = False
            is_host = True

        arena_map = get_map(room.map_id)
        spawn_x, spawn_y = arena_map.player_spawns[spawn_index]
        player = Player(
            player_id=uuid.uuid4().hex[:8],
            name=name.strip()[:16] or "Pixel Player",
            websocket=websocket,
            x=spawn_x,
            y=spawn_y,
            color=PLAYER_COLORS[spawn_index],
            is_host=is_host,
        )
        room.players[player.player_id] = player
        return player, None

    def get_room(self, room_code: str) -> Room | None:
        return self.rooms.get(room_code)

    def _snapshot(self, room: Room) -> dict:
        time_remaining = 0
        if room.status == "playing" and room.match_ends_at is not None:
            time_remaining = max(0, math.ceil(room.match_ends_at - time.monotonic()))

        scores = [player.score for player in room.players.values()]
        high_score = max(scores, default=0)
        winner_ids = [
            player.player_id
            for player in room.players.values()
            if room.status == "finished" and player.score == high_score
        ]

        return {
            "type": "state",
            "roomCode": room.code,
            "status": room.status,
            "timeRemaining": time_remaining,
            "winnerIds": winner_ids,
            "map": get_map(room.map_id).to_dict(),
            "availableMaps": map_summaries(),
            "events": [event for event in room.events if event["expiresAt"] > time.monotonic()],
            "coins": [
                {"id": coin.coin_id, "x": round(coin.x, 1), "y": round(coin.y, 1)}
                for coin in room.coins
            ],
            "speedBoost": (
                {"id": room.speed_boost.powerup_id, "x": round(room.speed_boost.x, 1), "y": round(room.speed_boost.y, 1)}
                if room.speed_boost is not None else None
            ),
            "players": [
                {
                    "id": player.player_id,
                    "name": player.name,
                    "x": round(player.x, 1),
                    "y": round(player.y, 1),
                    "color": player.color,
                    "isHost": player.is_host,
                    "isConnected": player.websocket is not None,
                    "score": player.score,
                    "speedBoostRemaining": round(
                        max(0.0, (player.speed_boost_until or 0.0) - time.monotonic()), 1
                    ),
                }
                for player in room.players.values()
            ],
        }

    async def broadcast(self, room: Room) -> None:
        """Send the current server-owned room state to every connected player."""
        message = self._snapshot(room)

        disconnected = []
        async with room.broadcast_lock:
            for player in list(room.players.values()):
                websocket = player.websocket
                if websocket is None:
                    continue
                try:
                    await websocket.send_json(message)
                except Exception as error:
                    logger.warning(
                        "Room state send failed for player %s in room %s: %s",
                        player.player_id,
                        room.code,
                        error,
                    )
                    disconnected.append((player.player_id, websocket))

        for player_id, websocket in disconnected:
            self._mark_disconnected(room, player_id, websocket)
        if disconnected and any(player.websocket is not None for player in room.players.values()):
            await self.broadcast(room)

    def set_input(self, room: Room, player_id: str, keys: set[str]) -> None:
        player = room.players.get(player_id)
        if player is not None:
            player.pending_keys.update(keys - player.keys)
            player.keys = keys

    def _new_coin(self, room: Room) -> Coin:
        """Choose a configured coin point that is clear of walls and players."""
        arena_map = get_map(room.map_id)
        if arena_map is None:
            raise ValueError(f"Unknown map: {room.map_id}")

        candidates = list(arena_map.coin_spawns)
        random.shuffle(candidates)
        for x, y in candidates:
            blocked = any(
                math.hypot(x - coin.x, y - coin.y) < COIN_RADIUS * 2
                for coin in room.coins
            )
            blocked = blocked or (
                room.speed_boost is not None
                and math.hypot(x - room.speed_boost.x, y - room.speed_boost.y) < COIN_RADIUS * 2
            )
            occupied = any(
                rectangles_overlap(
                    x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                    player.x, player.y, PLAYER_SIZE, PLAYER_SIZE,
                )
                for player in room.players.values()
            )
            inside_wall = any(
                rectangles_overlap(
                    x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                    obstacle.x, obstacle.y, obstacle.width, obstacle.height,
                )
                for obstacle in arena_map.obstacles
            )
            if not blocked and not occupied and not inside_wall:
                return Coin(uuid.uuid4().hex[:8], x, y)

        # Busy rooms can occupy every marked point, so look for another safe spot.
        for _ in range(100):
            x = random.uniform(COIN_RADIUS, ARENA_WIDTH - COIN_RADIUS)
            y = random.uniform(COIN_RADIUS, ARENA_HEIGHT - COIN_RADIUS)
            blocked = any(math.hypot(x - coin.x, y - coin.y) < COIN_RADIUS * 2 for coin in room.coins)
            blocked = blocked or (
                room.speed_boost is not None
                and math.hypot(x - room.speed_boost.x, y - room.speed_boost.y) < COIN_RADIUS * 2
            )
            occupied = any(
                rectangles_overlap(x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                                   player.x, player.y, PLAYER_SIZE, PLAYER_SIZE)
                for player in room.players.values()
            )
            solid = any(
                rectangles_overlap(x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                                   area.x, area.y, area.width, area.height)
                for area in arena_map.obstacles
            )
            penalty_zone = any(
                rectangles_overlap(x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                                   area.x, area.y, area.width, area.height)
                for area in (*arena_map.hazards, *arena_map.danger_zones)
            )
            if not blocked and not occupied and not solid and not penalty_zone:
                return Coin(uuid.uuid4().hex[:8], x, y)

        raise ValueError(f"Map {room.map_id} has no available coin spawn point")

    def _fill_coins(self, room: Room) -> None:
        while len(room.coins) < COIN_COUNT:
            room.coins.append(self._new_coin(room))

    def _new_speed_boost(self, room: Room) -> SpeedBoost:
        """Choose a safe map point for the room's one available speed boost."""
        arena_map = get_map(room.map_id)
        if arena_map is None:
            raise ValueError(f"Unknown map: {room.map_id}")

        def is_safe(x: float, y: float) -> bool:
            if x < COIN_RADIUS or y < COIN_RADIUS or x > ARENA_WIDTH - COIN_RADIUS or y > ARENA_HEIGHT - COIN_RADIUS:
                return False
            if any(math.hypot(x - coin.x, y - coin.y) < COIN_RADIUS * 2 for coin in room.coins):
                return False
            if any(
                rectangles_overlap(
                    x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                    player.x, player.y, PLAYER_SIZE, PLAYER_SIZE,
                )
                for player in room.players.values()
            ):
                return False
            if any(
                rectangles_overlap(
                    x - COIN_RADIUS, y - COIN_RADIUS, COIN_RADIUS * 2, COIN_RADIUS * 2,
                    area.x, area.y, area.width, area.height,
                )
                for area in (*arena_map.obstacles, *arena_map.hazards, *arena_map.danger_zones)
            ):
                return False
            return True

        candidates = list(arena_map.coin_spawns)
        random.shuffle(candidates)
        for x, y in candidates:
            if is_safe(x, y):
                return SpeedBoost(uuid.uuid4().hex[:8], x, y)

        # Keep the replacement safe even when every configured point is occupied.
        for _ in range(100):
            x = random.uniform(COIN_RADIUS, ARENA_WIDTH - COIN_RADIUS)
            y = random.uniform(COIN_RADIUS, ARENA_HEIGHT - COIN_RADIUS)
            if is_safe(x, y):
                return SpeedBoost(uuid.uuid4().hex[:8], x, y)

        raise ValueError(f"Map {room.map_id} has no available speed-boost spawn point")

    async def select_map(self, room: Room, player_id: str, map_id: str) -> str | None:
        player = room.players.get(player_id)
        if player is None or not player.is_host:
            return "Only the room host can choose the map."
        if room.status != "lobby":
            return "The map can only be changed before the match starts."
        arena_map = get_map(map_id)
        if arena_map is None:
            return "That map is not available."
        if len(arena_map.player_spawns) < MAX_PLAYERS:
            return "That map does not have enough valid player spawn points."
        if not all(valid_spawn(arena_map, x, y, PLAYER_SIZE) for x, y in arena_map.player_spawns):
            return "That map has an invalid player spawn point."

        room.map_id = map_id
        room.coins.clear()
        room.events.clear()
        for index, room_player in enumerate(room.players.values()):
            room_player.x, room_player.y = arena_map.player_spawns[index]
        await self.broadcast(room)
        return None

    async def start_match(self, room: Room, player_id: str) -> str | None:
        player = room.players.get(player_id)
        if player is None or not player.is_host:
            return "Only the room host can start or restart the match."
        if room.status == "playing":
            return "The match is already in progress."

        arena_map = get_map(room.map_id)
        if arena_map is None:
            return "The selected map is not available."
        if len(arena_map.player_spawns) < len(room.players):
            return "The selected map does not have enough player spawn points."
        if not all(valid_spawn(arena_map, x, y, PLAYER_SIZE) for x, y in arena_map.player_spawns):
            return "The selected map has invalid player spawn points."

        room.status = "playing"
        room.coins.clear()
        room.speed_boost = None
        room.events.clear()
        room.match_ends_at = time.monotonic() + MATCH_DURATION_SECONDS
        for index, room_player in enumerate(room.players.values()):
            room_player.x, room_player.y = arena_map.player_spawns[index]
            room_player.score = 0
            room_player.keys.clear()
            room_player.pending_keys.clear()
            room_player.penalty_cooldowns.clear()
            room_player.active_penalties.clear()
            room_player.speed_boost_until = None
        try:
            self._fill_coins(room)
            room.speed_boost = self._new_speed_boost(room)
        except ValueError as error:
            room.status = "lobby"
            room.match_ends_at = None
            room.coins.clear()
            room.speed_boost = None
            return str(error)
        await self.broadcast(room)
        return None

    def update_room(self, room: Room, now: float | None = None) -> None:
        """Advance one server tick. Separated out to make game rules easy to test."""
        if room.status != "playing" or not room.players:
            return

        current_time = time.monotonic() if now is None else now
        if room.match_ends_at is not None and current_time >= room.match_ends_at:
            room.status = "finished"
            room.match_ends_at = None
            room.coins.clear()
            room.speed_boost = None
            for player in room.players.values():
                player.keys.clear()
                player.pending_keys.clear()
                player.speed_boost_until = None
            return

        arena_map = get_map(room.map_id)
        if arena_map is None:
            return

        for player in room.players.values():
            if player.speed_boost_until is not None and current_time >= player.speed_boost_until:
                player.speed_boost_until = None
            active_keys = player.keys | player.pending_keys
            horizontal = int("right" in active_keys) - int("left" in active_keys)
            vertical = int("down" in active_keys) - int("up" in active_keys)
            diagonal_scale = 1 / math.sqrt(2) if horizontal and vertical else 1
            speed = PLAYER_SPEED * (
                SPEED_BOOST_MULTIPLIER
                if player.speed_boost_until is not None and current_time < player.speed_boost_until
                else 1
            )
            distance = speed * UPDATE_SECONDS * diagonal_scale

            # Resolve each axis separately so a blocked direction does not stop sliding along a wall.
            next_x = min(ARENA_WIDTH - PLAYER_SIZE, max(0, player.x + horizontal * distance))
            if not any(
                rectangles_overlap(next_x, player.y, PLAYER_SIZE, PLAYER_SIZE, wall.x, wall.y, wall.width, wall.height)
                for wall in arena_map.obstacles
            ):
                player.x = next_x

            next_y = min(ARENA_HEIGHT - PLAYER_SIZE, max(0, player.y + vertical * distance))
            if not any(
                rectangles_overlap(player.x, next_y, PLAYER_SIZE, PLAYER_SIZE, wall.x, wall.y, wall.width, wall.height)
                for wall in arena_map.obstacles
            ):
                player.y = next_y
            player.pending_keys.clear()

        for player in room.players.values():
            player_center_x = player.x + PLAYER_SIZE / 2
            player_center_y = player.y + PLAYER_SIZE / 2
            collected = [
                coin for coin in room.coins
                if math.hypot(player_center_x - coin.x, player_center_y - coin.y)
                <= COIN_RADIUS + PLAYER_SIZE / 2
            ]
            for coin in collected:
                room.coins.remove(coin)
                player.score += 10
                self._add_event(room, player, "coin", 10, coin.x, coin.y, current_time)
                room.coins.append(self._new_coin(room))

            boost = room.speed_boost
            if boost is not None and math.hypot(player_center_x - boost.x, player_center_y - boost.y) <= COIN_RADIUS + PLAYER_SIZE / 2:
                # Remove the shared item before replacement so another player cannot collect it too.
                room.speed_boost = None
                player.speed_boost_until = current_time + SPEED_BOOST_DURATION_SECONDS
                room.speed_boost = self._new_speed_boost(room)

            touching_zones = set()
            for zone, penalty in [
                *((area, 10) for area in arena_map.hazards),
                *((area, 5) for area in arena_map.danger_zones),
            ]:
                touching = rectangles_overlap(
                    player.x, player.y, PLAYER_SIZE, PLAYER_SIZE,
                    zone.x, zone.y, zone.width, zone.height,
                )
                if not touching:
                    continue
                touching_zones.add(zone.id)
                cooldown_until = player.penalty_cooldowns.get(zone.id, 0)
                if zone.id not in player.active_penalties and current_time >= cooldown_until:
                    player.score = max(0, player.score - penalty)
                    player.penalty_cooldowns[zone.id] = current_time + 2.0
                    self._add_event(room, player, "penalty", -penalty, player_center_x, player_center_y, current_time)
            player.active_penalties = touching_zones

        room.events = [event for event in room.events if event["expiresAt"] > current_time]

    def _add_event(self, room: Room, player: Player, kind: str, points: int, x: float, y: float, now: float) -> None:
        room.events.append({
            "id": uuid.uuid4().hex[:8],
            "playerId": player.player_id,
            "kind": kind,
            "points": points,
            "x": round(x, 1),
            "y": round(y, 1),
            "expiresAt": now + 1.5,
        })

    def _mark_disconnected(
        self,
        room: Room,
        player_id: str,
        websocket: WebSocket,
    ) -> bool:
        player = room.players.get(player_id)
        if player is None or player.websocket is not websocket:
            return False

        player.websocket = None
        player.disconnected_at = time.monotonic()
        player.keys.clear()
        player.pending_keys.clear()
        if player.is_host:
            next_host = next(
                (other for other in room.players.values() if other.websocket is not None),
                None,
            )
            if next_host is not None:
                player.is_host = False
                next_host.is_host = True
        return True

    def _expire_disconnected(self, room: Room, now: float) -> bool:
        expired_ids = [
            player.player_id
            for player in room.players.values()
            if player.websocket is None
            and player.disconnected_at is not None
            and now - player.disconnected_at >= RECONNECT_GRACE_SECONDS
        ]
        for player_id in expired_ids:
            self._remove_player(room, player_id)

        if expired_ids and not any(
            player.is_host and player.websocket is not None for player in room.players.values()
        ):
            next_host = next(
                (player for player in room.players.values() if player.websocket is not None),
                None,
            )
            if next_host is not None:
                next_host.is_host = True
        return bool(expired_ids)

    async def disconnect(self, room_code: str, player_id: str, websocket: WebSocket) -> None:
        room = self.rooms.get(room_code)
        if room is None:
            return

        if self._mark_disconnected(room, player_id, websocket):
            await self.broadcast(room)

    async def leave(self, room_code: str, player_id: str) -> None:
        """Remove a player immediately when they choose to leave the room."""
        room = self.rooms.get(room_code)
        if room is None:
            return

        removed_player = self._remove_player(room, player_id)
        if removed_player is None:
            return

        if removed_player.is_host:
            next_host = next(
                (player for player in room.players.values() if player.websocket is not None),
                None,
            )
            if next_host is not None:
                next_host.is_host = True

        if not room.players:
            self.rooms.pop(room_code, None)
        else:
            await self.broadcast(room)

    def _remove_player(self, room: Room, player_id: str) -> Player | None:
        return room.players.pop(player_id, None)

    async def update_loop(self) -> None:
        """Advance movement and the match clock at a steady server-controlled rate."""
        while True:
            await asyncio.sleep(UPDATE_SECONDS)
            await self.update_rooms()

    async def update_rooms(self) -> None:
        """Run one cleanup, movement, timer, and broadcast pass for every room."""
        now = time.monotonic()
        for room in list(self.rooms.values()):
            roster_changed = self._expire_disconnected(room, now)
            if not room.players:
                self.rooms.pop(room.code, None)
                continue

            if room.status == "playing":
                self.update_room(room, now)
                roster_changed = True

            if roster_changed:
                await self.broadcast(room)
