import asyncio
import time
import unittest

from maps import get_map, rectangles_overlap
from rooms import (
    ARENA_HEIGHT,
    ARENA_WIDTH,
    COIN_RADIUS,
    PLAYER_SIZE,
    PLAYER_SPEED,
    SPEED_BOOST_DURATION_SECONDS,
    SPEED_BOOST_MULTIPLIER,
    UPDATE_SECONDS,
    Coin,
    RoomManager,
    RECONNECT_GRACE_SECONDS,
    SpeedBoost,
)


class FakeWebSocket:
    """Small stand-in for a connected browser socket in room-manager tests."""

    def __init__(self):
        self.messages = []
        self.close_codes = []

    async def send_json(self, message):
        self.messages.append(message)

    async def close(self, code=1000, reason=""):
        self.close_codes.append((code, reason))


class RoomManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = RoomManager()

    async def add_player(self, code, name, is_host=False, token=None):
        player, error = await self.manager.add_player(
            code, name, is_host, FakeWebSocket(), resume_token=token
        )
        self.assertIsNone(error)
        self.assertIsNotNone(player)
        return player

    def test_reconnect_restores_identity_game_state_and_host_policy(self):
        asyncio.run(self._reconnect_restores_identity_game_state_and_host_policy())

    async def _reconnect_restores_identity_game_state_and_host_policy(self):
        host = await self.add_player("ROOM01", "Host", is_host=True)
        guest = await self.add_player("ROOM01", "Guest")
        room = self.manager.get_room("ROOM01")
        await self.manager.start_match(room, host.player_id)
        guest.x, guest.y, guest.score = 377.5, 214.0, 5

        old_socket = guest.websocket
        await self.manager.disconnect("ROOM01", guest.player_id, old_socket)
        self.assertIsNone(guest.websocket)
        self.assertEqual(len(room.players), 2)

        new_socket = FakeWebSocket()
        resumed, error = await self.manager.add_player(
            "ROOM01", "Guest", False, new_socket, resume_token=guest.resume_token
        )

        self.assertIsNone(error)
        self.assertIs(resumed, guest)
        self.assertEqual(resumed.player_id, guest.player_id)
        self.assertEqual((resumed.x, resumed.y, resumed.score), (377.5, 214.0, 5))
        self.assertEqual(room.status, "playing")
        self.assertEqual(len(room.players), 2)
        self.assertIs(resumed.websocket, new_socket)
        self.assertIsNone(resumed.disconnected_at)
        self.assertFalse(resumed.is_host)

    def test_host_disconnect_promotes_guest_and_guest_can_start_and_restart(self):
        asyncio.run(self._host_disconnect_promotes_guest_and_guest_can_start_and_restart())

    async def _host_disconnect_promotes_guest_and_guest_can_start_and_restart(self):
        host = await self.add_player("HOST01", "Host", is_host=True)
        guest = await self.add_player("HOST01", "Guest")
        room = self.manager.get_room("HOST01")

        await self.manager.disconnect("HOST01", host.player_id, host.websocket)
        self.assertTrue(guest.is_host)
        self.assertFalse(host.is_host)
        self.assertIsNone(await self.manager.start_match(room, guest.player_id))

        room.match_ends_at = time.monotonic() - 1
        self.manager.update_room(room)
        self.assertEqual(room.status, "finished")
        self.assertIsNone(await self.manager.start_match(room, guest.player_id))
        self.assertEqual(room.status, "playing")
        self.assertEqual([player.score for player in room.players.values()], [0, 0])

    def test_returning_former_host_does_not_take_host_from_promoted_player(self):
        asyncio.run(self._returning_former_host_does_not_take_host_from_promoted_player())

    async def _returning_former_host_does_not_take_host_from_promoted_player(self):
        host = await self.add_player("HOST02", "Host", is_host=True)
        guest = await self.add_player("HOST02", "Guest")
        room = self.manager.get_room("HOST02")
        await self.manager.disconnect("HOST02", host.player_id, host.websocket)
        self.assertTrue(guest.is_host)

        resumed, error = await self.manager.add_player(
            "HOST02", "Host", True, FakeWebSocket(), resume_token=host.resume_token
        )

        self.assertIsNone(error)
        self.assertIs(resumed, host)
        self.assertTrue(guest.is_host)
        self.assertFalse(host.is_host)
        self.assertEqual(sum(player.is_host for player in room.players.values()), 1)

    def test_replacing_a_socket_does_not_leave_a_duplicate_or_disconnect_the_new_socket(self):
        asyncio.run(self._replacing_a_socket_does_not_leave_a_duplicate_or_disconnect_the_new_socket())

    async def _replacing_a_socket_does_not_leave_a_duplicate_or_disconnect_the_new_socket(self):
        host = await self.add_player("SOCKET", "Host", is_host=True)
        guest = await self.add_player("SOCKET", "Guest")
        room = self.manager.get_room("SOCKET")
        old_socket = guest.websocket
        new_socket = FakeWebSocket()

        resumed, error = await self.manager.add_player(
            "SOCKET", "Guest", False, new_socket, resume_token=guest.resume_token
        )
        await self.manager.disconnect("SOCKET", guest.player_id, old_socket)

        self.assertIsNone(error)
        self.assertIs(resumed, guest)
        self.assertEqual(len(room.players), 2)
        self.assertIs(guest.websocket, new_socket)
        self.assertEqual(old_socket.close_codes[0][0], 4001)
        self.assertIsNotNone(host.websocket)

    def test_intentional_leave_removes_player_and_transfers_host_immediately(self):
        asyncio.run(self._intentional_leave_removes_player_and_transfers_host_immediately())

    async def _intentional_leave_removes_player_and_transfers_host_immediately(self):
        host = await self.add_player("LEAVE1", "Host", is_host=True)
        guest = await self.add_player("LEAVE1", "Guest")
        room = self.manager.get_room("LEAVE1")

        await self.manager.leave("LEAVE1", host.player_id)

        self.assertNotIn(host.player_id, room.players)
        self.assertTrue(guest.is_host)
        self.assertIsNone(host.disconnected_at)
        self.assertEqual(len(room.players), 1)

    def test_expired_token_cannot_create_or_join_as_a_new_player(self):
        asyncio.run(self._expired_token_cannot_create_or_join_as_a_new_player())

    async def _expired_token_cannot_create_or_join_as_a_new_player(self):
        host = await self.add_player("EXPIRE", "Host", is_host=True)
        guest = await self.add_player("EXPIRE", "Guest")
        room = self.manager.get_room("EXPIRE")
        await self.manager.disconnect("EXPIRE", host.player_id, host.websocket)
        host.disconnected_at = time.monotonic() - RECONNECT_GRACE_SECONDS - 1
        self.manager._expire_disconnected(room, time.monotonic())
        self.assertNotIn(host.player_id, room.players)
        self.assertTrue(guest.is_host)

        player, error = await self.manager.add_player(
            "EXPIRE", "Host", True, FakeWebSocket(), resume_token=host.resume_token
        )
        self.assertIsNone(player)
        self.assertIn("no longer belongs", error)
        self.assertEqual(len(room.players), 1)
        self.assertIs(self.manager.get_room("EXPIRE"), room)

        player, error = await self.manager.add_player(
            "EMPTY1", "Old host", True, FakeWebSocket(), resume_token="a" * 32
        )
        self.assertIsNone(player)
        self.assertIn("room has closed", error)
        self.assertIsNone(self.manager.get_room("EMPTY1"))

    def test_expired_disconnections_and_empty_rooms_are_cleaned_up(self):
        asyncio.run(self._expired_disconnections_and_empty_rooms_are_cleaned_up())

    async def _expired_disconnections_and_empty_rooms_are_cleaned_up(self):
        host = await self.add_player("CLEAN1", "Host", is_host=True)
        guest = await self.add_player("CLEAN1", "Guest")
        await self.manager.disconnect("CLEAN1", host.player_id, host.websocket)
        await self.manager.disconnect("CLEAN1", guest.player_id, guest.websocket)
        room = self.manager.get_room("CLEAN1")
        for player in room.players.values():
            player.disconnected_at = time.monotonic() - RECONNECT_GRACE_SECONDS - 1

        await self.manager.update_rooms()
        self.assertIsNone(self.manager.get_room("CLEAN1"))

    def test_room_limit_and_room_state_are_isolated(self):
        asyncio.run(self._room_limit_and_room_state_are_isolated())

    async def _room_limit_and_room_state_are_isolated(self):
        players = [await self.add_player("LIMIT1", "Host", is_host=True)]
        for index in range(7):
            players.append(await self.add_player("LIMIT1", f"Player {index}"))
        extra, error = await self.manager.add_player("LIMIT1", "Ninth", False, FakeWebSocket())
        self.assertIsNone(extra)
        self.assertEqual(error, "This room is full.")

        other_host = await self.add_player("OTHER1", "Other host", is_host=True)
        self.assertNotEqual(self.manager.get_room("LIMIT1"), self.manager.get_room("OTHER1"))
        self.assertEqual(len(self.manager.get_room("LIMIT1").players), 8)
        self.assertEqual(len(self.manager.get_room("OTHER1").players), 1)
        self.assertTrue(other_host.is_host)

    def test_movement_scores_coin_and_replaces_it(self):
        asyncio.run(self._movement_scores_coin_and_replaces_it())

    async def _movement_scores_coin_and_replaces_it(self):
        host = await self.add_player("COIN01", "Host", is_host=True)
        room = self.manager.get_room("COIN01")
        await self.manager.start_match(room, host.player_id)
        room.coins = [Coin("known-coin", host.x + 16, host.y + 16)]

        self.manager.set_input(room, host.player_id, {"right"})
        before_x = host.x
        self.manager.update_room(room)

        self.assertGreater(host.x, before_x)
        self.assertEqual(host.score, 10)
        self.assertEqual(len(room.coins), 1)
        self.assertNotEqual(room.coins[0].coin_id, "known-coin")

    def test_speed_boost_collection_replaces_it_safely_and_only_one_player_collects(self):
        asyncio.run(self._speed_boost_collection_replaces_it_safely_and_only_one_player_collects())

    async def _speed_boost_collection_replaces_it_safely_and_only_one_player_collects(self):
        host = await self.add_player("BOOST1", "Host", is_host=True)
        guest = await self.add_player("BOOST1", "Guest")
        room = self.manager.get_room("BOOST1")
        self.assertIsNone(await self.manager.start_match(room, host.player_id))

        now = time.monotonic()
        room.match_ends_at = now + 60
        room.coins.clear()
        # Place both players on the same server-owned item to verify it is consumed once.
        host.x, host.y = 300, 250
        guest.x, guest.y = 300, 250
        room.speed_boost = SpeedBoost("known-boost", 316, 266)

        self.manager.update_room(room, now)

        self.assertEqual(host.speed_boost_until, now + SPEED_BOOST_DURATION_SECONDS)
        self.assertIsNone(guest.speed_boost_until)
        self.assertIsNotNone(room.speed_boost)
        self.assertNotEqual(room.speed_boost.powerup_id, "known-boost")

        arena_map = get_map(room.map_id)
        spawn = room.speed_boost
        self.assertGreaterEqual(spawn.x, COIN_RADIUS)
        self.assertGreaterEqual(spawn.y, COIN_RADIUS)
        self.assertLessEqual(spawn.x, ARENA_WIDTH - COIN_RADIUS)
        self.assertLessEqual(spawn.y, ARENA_HEIGHT - COIN_RADIUS)
        self.assertFalse(any(
            rectangles_overlap(
                spawn.x - COIN_RADIUS, spawn.y - COIN_RADIUS,
                COIN_RADIUS * 2, COIN_RADIUS * 2,
                player.x, player.y, PLAYER_SIZE, PLAYER_SIZE,
            )
            for player in room.players.values()
        ))
        self.assertFalse(any(
            rectangles_overlap(
                spawn.x - COIN_RADIUS, spawn.y - COIN_RADIUS,
                COIN_RADIUS * 2, COIN_RADIUS * 2,
                area.x, area.y, area.width, area.height,
            )
            for area in (*arena_map.obstacles, *arena_map.hazards, *arena_map.danger_zones)
        ))
        self.assertFalse(any(
            ((spawn.x - coin.x) ** 2 + (spawn.y - coin.y) ** 2) ** 0.5 < COIN_RADIUS * 2
            for coin in room.coins
        ))

        snapshot = self.manager._snapshot(room)
        self.assertEqual(snapshot["speedBoost"]["id"], room.speed_boost.powerup_id)
        self.assertGreater(snapshot["players"][0]["speedBoostRemaining"], 0)

        await self.manager.broadcast(room)
        host_snapshot = host.websocket.messages[-1]
        guest_snapshot = guest.websocket.messages[-1]
        self.assertEqual(host_snapshot["speedBoost"], guest_snapshot["speedBoost"])
        self.assertEqual(
            host_snapshot["players"][0]["speedBoostRemaining"],
            guest_snapshot["players"][0]["speedBoostRemaining"],
        )

    def test_boosted_movement_is_one_point_five_times_normal_and_expires_after_five_seconds(self):
        asyncio.run(self._boosted_movement_is_one_point_five_times_normal_and_expires_after_five_seconds())

    async def _boosted_movement_is_one_point_five_times_normal_and_expires_after_five_seconds(self):
        host = await self.add_player("BOOST2", "Host", is_host=True)
        room = self.manager.get_room("BOOST2")
        self.assertIsNone(await self.manager.start_match(room, host.player_id))

        now = time.monotonic()
        room.match_ends_at = now + 60
        room.coins.clear()
        host.x, host.y = 400, 220
        host.speed_boost_until = now + SPEED_BOOST_DURATION_SECONDS
        self.manager.set_input(room, host.player_id, {"right"})
        before_x = host.x

        self.manager.update_room(room, now)
        boosted_distance = PLAYER_SPEED * SPEED_BOOST_MULTIPLIER * UPDATE_SECONDS
        self.assertAlmostEqual(host.x - before_x, boosted_distance)

        self.manager.update_room(room, now + SPEED_BOOST_DURATION_SECONDS)
        self.assertIsNone(host.speed_boost_until)
        self.assertAlmostEqual(host.x - before_x, boosted_distance + PLAYER_SPEED * UPDATE_SECONDS)

    def test_collecting_another_boost_refreshes_duration_without_stacking_speed(self):
        asyncio.run(self._collecting_another_boost_refreshes_duration_without_stacking_speed())

    async def _collecting_another_boost_refreshes_duration_without_stacking_speed(self):
        host = await self.add_player("BOOST3", "Host", is_host=True)
        room = self.manager.get_room("BOOST3")
        self.assertIsNone(await self.manager.start_match(room, host.player_id))

        now = time.monotonic()
        room.match_ends_at = now + 60
        room.coins.clear()
        host.x, host.y = 400, 220
        host.speed_boost_until = now + 2
        room.speed_boost = SpeedBoost("refresh-boost", host.x + 16, host.y + 16)
        self.manager.set_input(room, host.player_id, {"right"})
        before_x = host.x

        self.manager.update_room(room, now)

        one_boosted_tick = PLAYER_SPEED * SPEED_BOOST_MULTIPLIER * UPDATE_SECONDS
        self.assertAlmostEqual(host.x - before_x, one_boosted_tick)
        self.assertEqual(host.speed_boost_until, now + SPEED_BOOST_DURATION_SECONDS)

    def test_boosted_movement_keeps_arena_boundaries_and_wall_sliding(self):
        asyncio.run(self._boosted_movement_keeps_arena_boundaries_and_wall_sliding())

    async def _boosted_movement_keeps_arena_boundaries_and_wall_sliding(self):
        host = await self.add_player("BOOST4", "Host", is_host=True)
        room = self.manager.get_room("BOOST4")
        self.assertIsNone(await self.manager.start_match(room, host.player_id))

        now = time.monotonic()
        room.match_ends_at = now + 60
        room.coins.clear()
        host.speed_boost_until = now + 10
        host.x, host.y = 213, 160
        self.manager.set_input(room, host.player_id, {"right", "down"})
        self.manager.update_room(room, now)

        self.assertEqual(host.x, 213)
        self.assertAlmostEqual(host.y, 160 + PLAYER_SPEED * SPEED_BOOST_MULTIPLIER * UPDATE_SECONDS / (2 ** 0.5))

        host.x, host.y = 0, 0
        self.manager.set_input(room, host.player_id, {"left", "up"})
        self.manager.update_room(room, now + 0.1)
        self.assertEqual((host.x, host.y), (0, 0))
        self.assertLessEqual(host.x, ARENA_WIDTH - PLAYER_SIZE)
        self.assertLessEqual(host.y, ARENA_HEIGHT - PLAYER_SIZE)

    def test_restarting_match_clears_active_boost_state(self):
        asyncio.run(self._restarting_match_clears_active_boost_state())

    async def _restarting_match_clears_active_boost_state(self):
        host = await self.add_player("BOOST5", "Host", is_host=True)
        room = self.manager.get_room("BOOST5")
        self.assertIsNone(await self.manager.start_match(room, host.player_id))

        host.speed_boost_until = time.monotonic() + 30
        room.status = "finished"
        room.match_ends_at = None
        room.speed_boost = None

        self.assertIsNone(await self.manager.start_match(room, host.player_id))
        self.assertIsNone(host.speed_boost_until)
        self.assertIsNotNone(room.speed_boost)

    def test_speed_boosts_are_isolated_between_rooms(self):
        asyncio.run(self._speed_boosts_are_isolated_between_rooms())

    async def _speed_boosts_are_isolated_between_rooms(self):
        first_host = await self.add_player("BOOST6", "First host", is_host=True)
        second_host = await self.add_player("BOOST7", "Second host", is_host=True)
        first_room = self.manager.get_room("BOOST6")
        second_room = self.manager.get_room("BOOST7")
        self.assertIsNone(await self.manager.start_match(first_room, first_host.player_id))
        self.assertIsNone(await self.manager.start_match(second_room, second_host.player_id))

        now = time.monotonic()
        first_room.match_ends_at = second_room.match_ends_at = now + 60
        first_room.coins.clear()
        second_room.coins.clear()
        first_host.x, first_host.y = 300, 250
        first_room.speed_boost = SpeedBoost("first-room-boost", 316, 266)
        second_room.speed_boost = SpeedBoost("second-room-boost", 700, 400)
        second_boost = second_room.speed_boost

        self.manager.update_room(first_room, now)

        self.assertIsNotNone(first_host.speed_boost_until)
        self.assertIsNone(second_host.speed_boost_until)
        self.assertIs(second_room.speed_boost, second_boost)
        self.assertEqual(second_room.speed_boost.powerup_id, "second-room-boost")

    def test_arena_edges_and_obstacles_block_movement_while_allowing_wall_sliding(self):
        asyncio.run(self._arena_edges_and_obstacles_block_movement_while_allowing_wall_sliding())

    async def _arena_edges_and_obstacles_block_movement_while_allowing_wall_sliding(self):
        host = await self.add_player("WALL01", "Host", is_host=True)
        room = self.manager.get_room("WALL01")
        await self.manager.start_match(room, host.player_id)

        host.x, host.y = 213, 160
        self.manager.set_input(room, host.player_id, {"right", "down"})
        self.manager.update_room(room)
        self.assertEqual(host.x, 213)
        self.assertGreater(host.y, 160)

        host.x, host.y = 0, 0
        self.manager.set_input(room, host.player_id, {"left", "up"})
        self.manager.update_room(room)
        self.assertEqual((host.x, host.y), (0, 0))

        host.x, host.y = 928, 508
        self.manager.set_input(room, host.player_id, {"right", "down"})
        self.manager.update_room(room)
        self.assertEqual((host.x, host.y), (928, 508))

    def test_host_selects_map_and_snapshots_update_for_every_player(self):
        asyncio.run(self._host_selects_map_and_snapshots_update_for_every_player())

    async def _host_selects_map_and_snapshots_update_for_every_player(self):
        host = await self.add_player("MAP001", "Host", is_host=True)
        guest = await self.add_player("MAP001", "Guest")
        room = self.manager.get_room("MAP001")
        host_socket = host.websocket
        guest_socket = guest.websocket

        self.assertEqual(await self.manager.select_map(room, guest.player_id, "desert"), "Only the room host can choose the map.")
        self.assertEqual(await self.manager.select_map(room, host.player_id, "unknown"), "That map is not available.")
        self.assertIsNone(await self.manager.select_map(room, host.player_id, "frozen"))
        self.assertEqual(room.map_id, "frozen")
        self.assertEqual(host_socket.messages[-1]["map"]["id"], "frozen")
        self.assertEqual(guest_socket.messages[-1]["map"]["id"], "frozen")
        self.assertEqual(len(host_socket.messages[-1]["availableMaps"]), 4)

        self.assertIsNone(await self.manager.start_match(room, host.player_id))
        self.assertEqual(self.manager._snapshot(room)["map"]["id"], "frozen")
        self.assertTrue(all(coin.x >= 0 and coin.y >= 0 for coin in room.coins))
        self.assertEqual(await self.manager.select_map(room, host.player_id, "desert"), "The map can only be changed before the match starts.")

    def test_all_maps_have_valid_spawns_and_load_at_match_start(self):
        asyncio.run(self._all_maps_have_valid_spawns_and_load_at_match_start())

    async def _all_maps_have_valid_spawns_and_load_at_match_start(self):
        from maps import MAPS, valid_spawn
        from rooms import PLAYER_SIZE

        for map_id, arena_map in MAPS.items():
            self.assertEqual(len(arena_map.player_spawns), 8)
            for x, y in arena_map.player_spawns:
                self.assertTrue(valid_spawn(arena_map, x, y, PLAYER_SIZE), map_id)
            manager = RoomManager()
            host, error = await manager.add_player("LOAD01", "Host", True, FakeWebSocket())
            self.assertIsNone(error)
            room = manager.get_room("LOAD01")
            for index in range(7):
                player, error = await manager.add_player("LOAD01", f"Player {index}", False, FakeWebSocket())
                self.assertIsNone(error)
            self.assertIsNone(await manager.select_map(room, host.player_id, map_id))
            self.assertIsNone(await manager.start_match(room, host.player_id))
            self.assertEqual(room.map_id, map_id)
            self.assertEqual(len(room.coins), 8)
            self.assertEqual(manager._snapshot(room)["map"]["id"], map_id)

    def test_hazard_and_danger_penalties_have_cooldown_and_never_go_below_zero(self):
        asyncio.run(self._hazard_and_danger_penalties_have_cooldown_and_never_go_below_zero())

    async def _hazard_and_danger_penalties_have_cooldown_and_never_go_below_zero(self):
        host = await self.add_player("PEN001", "Host", is_host=True)
        room = self.manager.get_room("PEN001")
        await self.manager.start_match(room, host.player_id)

        host.x, host.y, host.score = 80, 350, 20
        now = time.monotonic()
        self.manager.update_room(room, now)
        self.assertEqual(host.score, 10)
        self.assertEqual(room.events[-1]["points"], -10)
        self.manager.update_room(room, now + 1)
        self.assertEqual(host.score, 10)
        self.manager.update_room(room, now + 2.1)
        self.assertEqual(host.score, 10)

        host.x, host.y = 300, 250
        self.manager.update_room(room, now + 2.2)
        host.x, host.y, host.score = 80, 350, 10
        self.manager.update_room(room, now + 4.3)
        self.assertEqual(host.score, 0)
        self.assertEqual(room.events[-1]["points"], -10)

        host.x, host.y, host.score = 770, 140, 3
        self.manager.update_room(room, now + 6.4)
        self.assertEqual(host.score, 0)
        self.assertEqual(room.events[-1]["points"], -5)

    def test_finished_match_reports_tied_winners(self):
        asyncio.run(self._finished_match_reports_tied_winners())

    async def _finished_match_reports_tied_winners(self):
        host = await self.add_player("TIE001", "Host", is_host=True)
        guest = await self.add_player("TIE001", "Guest")
        room = self.manager.get_room("TIE001")
        await self.manager.start_match(room, host.player_id)
        host.score = guest.score = 2
        room.match_ends_at = time.monotonic() - 1

        self.manager.update_room(room)

        snapshot = self.manager._snapshot(room)
        self.assertEqual(room.status, "finished")
        self.assertEqual(set(snapshot["winnerIds"]), {host.player_id, guest.player_id})


if __name__ == "__main__":
    unittest.main()
