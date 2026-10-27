"""Run browser-like multi-client checks against a running FastAPI server.

Start the backend with PIXEL_BATTLE_MATCH_SECONDS=5, then run:
    python tests/websocket_smoke.py
"""

import asyncio
import json
import math
import os
import uuid

import websockets

WS_BASE_URL = os.environ.get("WS_BASE_URL", "ws://127.0.0.1:8000")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")


async def open_player(room_code, name, is_host=False, resume_token=None, origin=FRONTEND_ORIGIN):
    socket = await websockets.connect(
        f"{WS_BASE_URL.rstrip('/')}/ws/{room_code}",
        origin=origin,
    )
    join_message = {"type": "join", "name": name, "isHost": is_host}
    if resume_token is not None:
        join_message["resumeToken"] = resume_token
    await socket.send(json.dumps(join_message))
    response = json.loads(await asyncio.wait_for(socket.recv(), timeout=3))
    if response.get("type") == "error":
        await socket.close()
        return None, response
    assert response["type"] == "joined", response
    state = await receive_state(socket)
    return (socket, response, state), None


async def receive_state(socket, condition=lambda state: True, timeout=3):
    async def read_until_match():
        while True:
            message = json.loads(await socket.recv())
            if message.get("type") == "error":
                raise AssertionError(message)
            if message.get("type") == "state" and condition(message):
                return message

    return await asyncio.wait_for(read_until_match(), timeout=timeout)


def get_player(state, player_id):
    return next(player for player in state["players"] if player["id"] == player_id)


async def collect_one_coin(socket, player_id, state):
    starting_score = get_player(state, player_id)["score"]
    for _ in range(60):
        current_player = get_player(state, player_id)
        if current_player["score"] > starting_score:
            await socket.send(json.dumps({"type": "input", "keys": []}))
            return state

        coin = min(
            state["coins"],
            key=lambda item: math.hypot(
                item["x"] - (current_player["x"] + 16),
                item["y"] - (current_player["y"] + 16),
            ),
        )
        dx = coin["x"] - (current_player["x"] + 16)
        dy = coin["y"] - (current_player["y"] + 16)
        if math.hypot(dx, dy) <= 26:
            keys = []
        elif abs(dx) >= abs(dy):
            keys = ["right"] if dx > 0 else ["left"]
        else:
            keys = ["down"] if dy > 0 else ["up"]

        await socket.send(json.dumps({"type": "input", "keys": keys}))
        state = await receive_state(socket)

    raise AssertionError("Player did not collect a coin during the WebSocket check")


async def main():
    live_room_code = uuid.uuid4().hex[:6].upper()
    limit_room_code = uuid.uuid4().hex[:6].upper()
    other_room_code = uuid.uuid4().hex[:6].upper()

    # Invalid and nonexistent room codes return understandable server errors.
    _, error = await open_player("BAD", "Bad code")
    assert "six letters or numbers" in error["message"], error
    _, error = await open_player("NOEXST", "Missing room")
    assert "Room not found" in error["message"], error
    rejected_origin_socket = await websockets.connect(
        f"{WS_BASE_URL.rstrip('/')}/ws/ORIGIN",
        origin="https://untrusted.example",
    )
    error = json.loads(await asyncio.wait_for(rejected_origin_socket.recv(), timeout=3))
    assert "not allowed" in error["message"], error
    print("Room-code and WebSocket-origin validation: passed")

    # Two real WebSocket clients synchronize movement, scoring, and refresh resume.
    host_info, error = await open_player(live_room_code, "Host", is_host=True)
    assert error is None
    host, _, _ = host_info
    guest_info, error = await open_player(live_room_code, "Guest")
    assert error is None
    guest, guest_joined, guest_state = guest_info

    await host.send(json.dumps({"type": "select_map", "mapId": "desert"}))
    host_map_state = await receive_state(host, lambda state: state["map"]["id"] == "desert")
    guest_map_state = await receive_state(guest, lambda state: state["map"]["id"] == "desert")
    assert host_map_state["map"]["id"] == guest_map_state["map"]["id"] == "desert"
    assert len(guest_map_state["map"]["obstacles"]) > 0

    await host.send(json.dumps({"type": "start_match"}))
    await receive_state(host, lambda state: state["status"] == "playing")
    guest_state = await receive_state(guest, lambda state: state["status"] == "playing")
    guest_id = guest_joined["playerId"]
    before = get_player(guest_state, guest_id)

    await guest.send(json.dumps({"type": "input", "keys": ["left"]}))
    moved_state = await receive_state(
        guest,
        lambda state: get_player(state, guest_id)["x"] < before["x"],
    )
    moved_player = get_player(moved_state, guest_id)
    host_moved = await receive_state(
        host,
        lambda state: get_player(state, guest_id)["x"] <= moved_player["x"],
    )
    assert get_player(host_moved, guest_id)["x"] == moved_player["x"]

    scored_state = await collect_one_coin(guest, guest_id, moved_state)
    scored_player = get_player(scored_state, guest_id)
    assert scored_player["score"] >= 10
    host_scored = await receive_state(
        host,
        lambda state: get_player(state, guest_id)["score"] >= scored_player["score"],
    )
    assert get_player(host_scored, guest_id)["score"] == scored_player["score"]
    saved_state = (scored_player["x"], scored_player["y"], scored_player["score"])

    await guest.close()
    await receive_state(
        host,
        lambda state: not get_player(state, guest_id)["isConnected"],
    )
    resumed_info, error = await open_player(
        live_room_code, "Guest", resume_token=guest_joined["resumeToken"]
    )
    assert error is None
    resumed, resumed_joined, resumed_state = resumed_info
    assert resumed_joined["playerId"] == guest_id
    assert resumed_state["status"] == "playing"
    assert len(resumed_state["players"]) == 2
    restored = get_player(resumed_state, guest_id)
    assert (restored["x"], restored["y"], restored["score"]) == saved_state
    print("Two-client map sync, movement, 10-point scoring, and in-match refresh: passed")

    # The connected guest is promoted when the host socket closes, can finish,
    # and can start the next match as host.
    await host.close()
    promoted_state = await receive_state(
        resumed,
        lambda state: get_player(state, guest_id)["isHost"],
    )
    assert get_player(promoted_state, guest_id)["isHost"]
    finished = await receive_state(
        resumed,
        lambda state: state["status"] == "finished",
        timeout=8,
    )
    assert finished["status"] == "finished"
    await resumed.send(json.dumps({"type": "start_match"}))
    restarted = await receive_state(
        resumed,
        lambda state: state["status"] == "playing",
    )
    assert all(player["score"] == 0 for player in restarted["players"])
    print("Host disconnect, promotion, match end, and restart: passed")
    await resumed.close()

    # Eight players fit, a ninth is rejected, and another room stays independent.
    first_room, error = await open_player(limit_room_code, "Host", is_host=True)
    assert error is None
    clients = [first_room[0]]
    for index in range(7):
        joined, error = await open_player(limit_room_code, f"Player{index}")
        assert error is None
        clients.append(joined[0])
    _, error = await open_player(limit_room_code, "Ninth")
    assert error and "room is full" in error["message"], error

    second_room, error = await open_player(other_room_code, "Other host", is_host=True)
    assert error is None
    await clients[0].send(json.dumps({"type": "start_match"}))
    first_state = await receive_state(
        clients[0],
        lambda state: state["status"] == "playing",
    )
    second_state = second_room[2]
    assert first_state["roomCode"] == limit_room_code
    assert second_state["roomCode"] == other_room_code
    assert second_state["status"] == "lobby"
    assert len(first_state["players"]) == 8
    assert len(second_state["players"]) == 1
    print("Eight-player capacity and separate-room isolation: passed")

    for socket in clients + [second_room[0]]:
        await socket.close()


if __name__ == "__main__":
    asyncio.run(main())
