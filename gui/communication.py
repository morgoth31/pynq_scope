import asyncio
import httpx
import websockets
import numpy as np

class ServerCommunicator:
    def __init__(self, server_ip):
        self.server_ip = server_ip
        self.websocket = None
        self.stop_event = asyncio.Event()

    async def connect(self):
        uri = f"ws://{self.server_ip}/ws/data"
        try:
            self.websocket = await websockets.connect(uri)
            print("Client WebSocket connecté.")
            return True
        except Exception as e:
            print(f"Erreur de connexion WebSocket: {e}")
            return False

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            print("Client WebSocket déconnecté.")

    async def data_receiver(self, data_callback):
        if not self.websocket:
            return

        while not self.stop_event.is_set():
            try:
                data_bytes = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                # Reshape the data into 8 channels
                data_chunk = np.frombuffer(data_bytes, dtype=np.int16).reshape(8, -1)
                data_callback(data_chunk)
            except asyncio.TimeoutError:
                pass
            except websockets.exceptions.ConnectionClosed:
                print("Connexion WebSocket fermée par le serveur.")
                break

    async def control_api(self, action: str, params: dict = None, is_config: bool = False):
        if is_config:
            url = f"http://{self.server_ip}/configure"
            payload = {"action": action, "params": params or {}}
        else:
            url = f"http://{self.server_ip}/{action}"
            payload = params

        try:
            async with httpx.AsyncClient() as client:
                if payload:
                    response = await client.post(url, json=payload)
                else:
                    response = await client.post(url)

                print(f"API [POST /{action}]: Réponse {response.status_code} -> {response.json()}")
                return response.json()
        except httpx.ConnectError as e:
            print(f"Erreur de connexion API: {e}")
            return None

    async def get_status(self):
        url = f"http://{self.server_ip}/status"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                return response.json()
        except httpx.ConnectError as e:
            print(f"Erreur de connexion API: {e}")
            return None
