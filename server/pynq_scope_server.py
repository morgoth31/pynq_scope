import asyncio
import numpy as np
import uvicorn
import logging
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
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

    def __init__(self):
        """Initializes the AcquisitionManager."""
        self.active_connections: List[WebSocket] = []
        self.is_running: bool = False
        self.acquisition_task: asyncio.Task | None = None

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

    async def _acquisition_loop(self):
        """
        Asynchronous task that simulates data acquisition and broadcasts it to clients.
        """
        logger.info("Début de l'acquisition...")
        self.is_running = True
        try:
            while self.is_running:
                try:
                    array_0, _, _, _, _, _, _, _ = dma.acquire_data(SAMPLE_RATE, CHUNK_SIZE)
                    data_bytes = array_0.tobytes()
                    if self.active_connections:
                        await self.broadcast(data_bytes)
                    await asyncio.sleep(CHUNK_SIZE / SAMPLE_RATE)
                except Exception as e:
                    logger.error(f"Erreur dans la boucle d'acquisition: {e}")
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info("Tâche d'acquisition annulée.")
        finally:
            self.is_running = False
            logger.info("Fin de l'acquisition.")

    def start_acquisition(self):
        """
        Starts the data acquisition task if it is not already running.

        Returns:
            A dictionary with the status of the operation.
        """
        if not self.is_running:
            self.acquisition_task = asyncio.create_task(self._acquisition_loop())
            return {"status": "Acquisition démarrée"}
        return {"status": "Acquisition déjà en cours"}

    def stop_acquisition(self):
        """
        Stops the data acquisition task.

        Returns:
            A dictionary with the status of the operation.
        """
        if self.is_running and self.acquisition_task:
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
            return {"status": "Action traitée", "action": action}
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'action '{action}': {e}")
            return {"status": "erreur", "message": str(e)}

# --- Initialisation de FastAPI et du Manager ---
app = FastAPI()
manager = AcquisitionManager()
dma = dmaAcquisition("activ_filter_one_7010.bit")

# --- Points de terminaison (Endpoints) ---

@app.post("/start")
async def api_start():
    """Endpoint de contrôle pour démarrer l'acquisition."""
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
    print("Lancement du serveur sur http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)

