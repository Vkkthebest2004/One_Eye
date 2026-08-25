import asyncio
import json
import websockets

async def test_ws():
    uri = "ws://localhost:8001/ws"
    print(f"Connecting to WebSocket at {uri}...")
    async with websockets.connect(uri) as websocket:
        print("Connected! Listening for broadcast events (3 seconds)...")
        # Send ping
        await websocket.send("ping")
        resp = await websocket.recv()
        print(f"Received pong response: {resp}")
        
        # Listen for real-time detection/camera status updates
        try:
            msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
            data = json.loads(msg)
            print(f"Received real-time message type: {data.get('type')}")
        except asyncio.TimeoutError:
            print("No immediate broadcast within timeout, connection verified OK.")

if __name__ == "__main__":
    asyncio.run(test_ws())
