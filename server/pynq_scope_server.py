import asyncio
import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
from dma_acquisition import dmaAcquisition

# --- Configuration de l'Acquisition ---
SAMPLE_RATE = 1000  # Echantillons/seconde
CHUNK_SIZE = 100    # Echantillons par envoi
DTYPE = np.int16    # Type de données des échantillons

# --- Classe pour gérer l'état et la diffusion ---
class AcquisitionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.is_running: bool = False
        self.acquisition_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket):
        """Accepte un nouveau client WebSocket et l'ajoute à la liste."""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connecté. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Retire un client WebSocket de la liste."""
        self.active_connections.remove(websocket)
        print(f"Client déconnecté. Total: {len(self.active_connections)}")

    async def broadcast(self, data: bytes):
        """Diffuse des données binaires à tous les clients connectés."""
        # Utilise un 'gather' pour envoyer en parallèle à tous les clients
        results = await asyncio.gather(
            *[client.send_bytes(data) for client in self.active_connections],
            return_exceptions=True
        )
        # Gère les clients qui se seraient déconnectés pendant l'envoi
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Erreur envoi client {i}: {result}. Déconnexion.")
                # Note: La déconnexion est gérée par le 'finally' du /ws/data

    async def _acquisition_loop(self):
        """Tâche asynchrone simulant l'acquisition de données."""
        print("Début de l'acquisition...")
        self.is_running = True
        try:
            while self.is_running:
                # 1. Acquerir les données
                array_0, _, _, _, _, _, _, _ = dma.acquire_data(SAMPLE_RATE, CHUNK_SIZE)

                # 2. Sérialiser en binaire (critique pour la performance)
                data_bytes = array_0.tobytes()

                # 3. Diffuser les données
                if self.active_connections:
                    await self.broadcast(data_bytes)

                # 4. Attendre pour simuler la fréquence d'échantillonnage
                await asyncio.sleep(CHUNK_SIZE / SAMPLE_RATE)
        
        except asyncio.CancelledError:
            print("Tâche d'acquisition annulée.")
        finally:
            self.is_running = False
            print("Fin de l'acquisition.")

    def start_acquisition(self):
        """Démarre la tâche d'acquisition si elle n'est pas déjà en cours."""
        if not self.is_running:
            self.acquisition_task = asyncio.create_task(self._acquisition_loop())
            return {"status": "Acquisition démarrée"}
        return {"status": "Acquisition déjà en cours"}

    def stop_acquisition(self):
        """Arrête la tâche d'acquisition."""
        if self.is_running and self.acquisition_task:
            self.acquisition_task.cancel()
            self.acquisition_task = None
            return {"status": "Acquisition arrêtée"}
        return {"status": "Acquisition non démarrée"}

    async def handle_action(self, action: str, params: Dict[str, Any]):
        """Gère une action de configuration."""
        print(f"Action reçue: {action} avec les paramètres: {params}")
        # Logique de distribution des actions
        if action == "set_sample_rate":
            global SAMPLE_RATE
            SAMPLE_RATE = params.get("value", SAMPLE_RATE)
        return {"status": "Action traitée", "action": action}

# --- Initialisation de FastAPI et du Manager ---
app = FastAPI()
manager = AcquisitionManager()
dma = dmaAcquisition()

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

