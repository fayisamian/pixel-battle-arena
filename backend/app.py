import asyncio
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from rooms import RoomManager

room_manager = RoomManager()
ALLOWED_KEYS = {"up", "down", "left", "right"}
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "PIXEL_BATTLE_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    update_task = asyncio.create_task(room_manager.update_loop())
    try:
        yield
    finally:
        update_task.cancel()
        try:
            await update_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Pixel Battle Arena API", lifespan=lifespan)


@app.get("/")
def read_root():
    """Confirm that the backend is running."""
    return {"message": "Pixel Battle Arena backend is running"}


async def send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json({"type": "error", "message": message})
    await websocket.close(code=1008)


@app.websocket("/ws/{room_code}")
async def room_websocket(websocket: WebSocket, room_code: str):
    room_code = room_code.upper()
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.accept()
        await send_error(websocket, "This website is not allowed to connect to the game server.")
        return

    await websocket.accept()
    player = None

    try:
        join_message = await websocket.receive_json()
        if not isinstance(join_message, dict) or join_message.get("type") != "join":
            await send_error(websocket, "Send a join message to enter the room.")
            return

        if not re.fullmatch(r"[A-Z0-9]{6}", room_code):
            await send_error(websocket, "Room codes must have six letters or numbers.")
            return

        name = join_message.get("name", "Pixel Player")
        is_host = join_message.get("isHost")
        resume_token = join_message.get("resumeToken")
        if (
            not isinstance(name, str)
            or not isinstance(is_host, bool)
            or (
                resume_token is not None
                and (
                    not isinstance(resume_token, str)
                    or not re.fullmatch(r"[0-9a-f]{32}", resume_token)
                )
            )
        ):
            await send_error(websocket, "The join message has an invalid name or player role.")
            return

        player, error = await room_manager.add_player(
            room_code=room_code,
            name=name,
            is_host=is_host,
            websocket=websocket,
            resume_token=resume_token,
        )
        if error:
            await send_error(websocket, error)
            return

        room = room_manager.get_room(room_code)
        await websocket.send_json({
            "type": "joined",
            "playerId": player.player_id,
            "resumeToken": player.resume_token,
        })
        await room_manager.broadcast(room)

        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await send_error(websocket, "Messages must be JSON objects.")
                break

            current_player = room.players.get(player.player_id)
            if current_player is None or current_player.websocket is not websocket:
                await websocket.close(code=4001, reason="Room session is active in another connection")
                break

            message_type = message.get("type")
            if message_type == "input":
                keys = message.get("keys")
                if (
                    not isinstance(keys, list)
                    or any(not isinstance(key, str) or key not in ALLOWED_KEYS for key in keys)
                ):
                    await send_error(websocket, "Movement input must contain arrow directions only.")
                    break
                if room.status == "playing":
                    room_manager.set_input(room, player.player_id, set(keys))
            elif message_type == "select_map":
                map_id = message.get("mapId")
                if not isinstance(map_id, str):
                    await websocket.send_json({"type": "error", "message": "Choose a valid map."})
                    continue
                error = await room_manager.select_map(room, player.player_id, map_id)
                if error:
                    await websocket.send_json({"type": "error", "message": error})
            elif message_type == "start_match":
                error = await room_manager.start_match(room, player.player_id)
                if error:
                    await websocket.send_json({"type": "error", "message": error})
            elif message_type == "leave":
                await room_manager.leave(room_code, player.player_id)
                player = None
                break
            else:
                await websocket.send_json({"type": "error", "message": "Unknown message type."})

    except WebSocketDisconnect:
        pass
    except ValueError:
        try:
            await send_error(websocket, "Messages must contain valid JSON.")
        except RuntimeError:
            pass
    finally:
        if player is not None:
            await room_manager.disconnect(room_code, player.player_id, websocket)
