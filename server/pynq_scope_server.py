import asyncio
import numpy as np
import uvicorn
import logging
import argparse
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import time

try:
    # This import works when running tests from the project root
    from server.dma_acquisition import dmaAcquisition
except ModuleNotFoundError:
    # This import works when running the server directly from the server directory
    from dma_acquisition import dmaAcquisition

import os

# --- Configuration du Logging ---
if not os.path.exists("logs"):
    os.makedirs("logs")
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler = TimedRotatingFileHandler("logs/server.log", when="midnight", interval=1, backupCount=7)
log_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# --- Configuration de l'Acquisition ---
SAMPLE_RATE = 1000  # Echantillons/seconde
CHUNK_SIZE = 100    # Echantillons par envoi
DTYPE = np.int16    # Type de données des échantillons
BITSTREAM = "activ_filter_one_7010.bit"



# --- Classe pour gérer l'état et la diffusion ---
class AcquisitionManager:
    """Manages data acquisition, WebSocket connections, and data broadcasting."""

    def __init__(self, emulate: bool = False):
        """Initializes the AcquisitionManager."""
        self.active_connections: List[WebSocket] = []
        self.is_running: bool = False
        self.acquisition_task: asyncio.Task | None = None
        self.emulate = emulate
        if self.emulate:
            self.t = np.linspace(0, 1, SAMPLE_RATE, endpoint=False)
            self.phase = 0
        self.data_buffer = []

    async def connect(self, websocket: WebSocket):
        """
        Accepts a new WebSocket connection and adds it to the list of active connections.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connecté. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        Removes a WebSocket connection from the list of active connections.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self.active_connections.remove(websocket)
        logger.info(f"Client déconnecté. Total: {len(self.active_connections)}")

    async def broadcast(self, data: bytes):
        """
        Broadcasts binary data to all connected WebSocket clients.

        Args:
            data: The binary data to broadcast.
        """
        results = await asyncio.gather(
            *[client.send_bytes(data) for client in self.active_connections],
            return_exceptions=True
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erreur envoi client {i}: {result}. Déconnexion.")

    async def _acquisition_loop(self, mode: str = "auto", duration: int = 0):
        """
        Asynchronous task that simulates data acquisition and broadcasts it to clients.
        """
        logger.info(f"Début de l'acquisition en mode {mode} pour une durée de {duration}s...")
        self.data_buffer.clear()

        start_time = time.time()

        try:
            while self.is_running:
                if mode == "timed" and time.time() - start_time >= duration:
                    break

                try:
                    if self.emulate:
                        # Emulation: 8 channels with different frequencies
                        amplitude = 2**14
                        indices = np.arange(self.phase, self.phase + CHUNK_SIZE)

                        channels = []
                        for i in range(8):
                            freq = 50 * (i + 1)
                            signal = amplitude * np.sin(2 * np.pi * freq * indices / SAMPLE_RATE)
                            channels.append(signal.astype(DTYPE))

                        self.phase = (self.phase + CHUNK_SIZE) % SAMPLE_RATE

                        data_array = np.stack(channels)

                    else:
                        # Real mode: DMA acquisition
                        arrays = dma.acquire_data(SAMPLE_RATE, CHUNK_SIZE)
                        data_array = np.stack(arrays)

                    self.data_buffer.append(data_array)
                    data_bytes = data_array.tobytes()
                    if self.active_connections:
                        await self.broadcast(data_bytes)
                    await asyncio.sleep(CHUNK_SIZE / SAMPLE_RATE)
                except Exception as e:
                    logger.error(f"Erreur dans la boucle d'acquisition: {e}")
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info("Tâche d'acquisition annulée.")
        finally:
            logger.info("Fin de l'acquisition.")
            if mode == "timed":
                asyncio.create_task(self.save_recorded_data(self.data_buffer))

    async def save_recorded_data(self, data_buffer):
        """Saves the recorded data to a CSV file."""
        if not os.path.exists("data"):
            os.makedirs("data")
        filename = f"data/record_{int(time.time())}.csv"

        # Data is a list of (channels, chunk_size) arrays
        # We need to concatenate and transpose
        all_data = np.concatenate(data_buffer, axis=1).T

        np.savetxt(filename, all_data, delimiter=",", fmt='%d',
                   header=",".join([f"Channel {i}" for i in range(8)]), comments="")
        logger.info(f"Données enregistrées dans {filename}")


    def start_acquisition(self, mode: str = "auto", duration: int = 0):
        """
        Starts the data acquisition task if it is not already running.

        Returns:
            A dictionary with the status of the operation.
        """
        if not self.is_running:
            self.is_running = True
            self.acquisition_task = asyncio.create_task(self._acquisition_loop(mode, duration))
            return {"status": "Acquisition démarrée"}
        return {"status": "Acquisition déjà en cours"}

    def stop_acquisition(self):
        """
        Stops the data acquisition task.

        Returns:
            A dictionary with the status of the operation.
        """
        if self.is_running and self.acquisition_task:
            self.is_running = False
            self.acquisition_task.cancel()
            self.acquisition_task = None
            return {"status": "Acquisition arrêtée"}
        return {"status": "Acquisition non démarrée"}

    async def handle_action(self, action: str, params: Dict[str, Any]):
        """
        Handles a configuration action.

        Args:
            action: The action to handle.
            params: The parameters for the action.

        Returns:
            A dictionary with the status of the operation.
        """
        logger.info(f"Action reçue: {action} avec les paramètres: {params}")
        try:
            if action == "set_sample_rate":
                global SAMPLE_RATE
                SAMPLE_RATE = params.get("value", SAMPLE_RATE)
            elif action == "save_to_csv":
                await self.save_recorded_data(self.data_buffer)

            return {"status": "Action traitée", "action": action}
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'action '{action}': {e}")
            return {"status": "erreur", "message": str(e)}

# --- Initialisation de FastAPI et du Manager ---
app = FastAPI()
dma = None  # Sera initialisé plus tard si nécessaire
manager = None  # Sera initialisé dans le main

# --- Points de terminaison (Endpoints) ---

@app.post("/start")
async def api_start(params: Dict[str, Any] = None):
    """Endpoint de contrôle pour démarrer l'acquisition."""
    if params:
        mode = params.get("mode", "auto")
        duration = params.get("duration", 0)
        return manager.start_acquisition(mode, duration)
    return manager.start_acquisition()

@app.post("/stop")
async def api_stop():
    """Endpoint de contrôle pour arrêter l'acquisition."""
    return manager.stop_acquisition()

@app.get("/status")
async def api_status():
    """Endpoint pour vérifier l'état."""
    return {"running": manager.is_running, "clients": len(manager.active_connections)}

@app.post("/configure")
async def api_configure(config: Dict[str, Any]):
    """Endpoint pour la configuration dynamique."""
    action = config.get("action")
    params = config.get("params", {})
    if not action:
        return {"error": "Aucune action spécifiée"}
    return await manager.handle_action(action, params)

@app.websocket("/ws/data")
async def websocket_data(websocket: WebSocket):
    """Point de terminaison WebSocket pour le flux de données."""
    await manager.connect(websocket)
    try:
        while True:
            # Maintient la connexion ouverte pour recevoir les 'pings'
            # ou d'éventuels messages du client.
            # Pour un flux purement descendant, on attend simplement.
            await websocket.receive_text() # En attente passive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Erreur WebSocket: {e}")
        manager.disconnect(websocket)

# --- Point d'entrée pour Uvicorn ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur FastAPI pour PYNQ Scope")
    parser.add_argument("--emulate", action="store_true", help="Activer le mode d'émulation sans DMA.")
    args = parser.parse_args()

    # Initialisation du manager avec le mode d'émulation
    manager = AcquisitionManager(emulate=args.emulate)

    # Initialisation du DMA seulement si on n'est pas en mode émulation
    if not args.emulate:
        dma = dmaAcquisition(BITSTREAM)
        logger.info("DMA initialisé.")
    else:
        logger.info("Mode d'émulation activé. Le DMA ne sera pas utilisé.")

    print("Lancement du serveur sur http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

