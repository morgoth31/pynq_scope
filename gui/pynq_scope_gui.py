import asyncio
import httpx
import websockets
import numpy as np

# --- Correspondance avec la configuration serveur ---
CHUNK_SIZE = 100
DTYPE = np.int16
SERVER_URL = "127.0.0.1:8000"

async def data_receiver(stop_event: asyncio.Event):
    """Se connecte au WebSocket et reçoit les données binaires."""
    uri = f"ws://{SERVER_URL}/ws/data"
    try:
        async with websockets.connect(uri) as websocket:
            print("Client WebSocket connecté.")
            while not stop_event.is_set():
                try:
                    # Attendre les données binaires
                    data_bytes = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    # Désérialiser les bytes en tableau NumPy
                    data_chunk = np.frombuffer(data_bytes, dtype=DTYPE)
                    
                    # Traitement (ici, simple affichage)
                    print(f"Reçu chunk: {data_chunk.shape} | "
                          f"Ex: {data_chunk[0]} | "
                          f"Moy: {data_chunk.mean():.2f}")
                
                except asyncio.TimeoutError:
                    # Pas de données reçues, c'est normal si l'acquisition est arrêtée
                    pass
                except websockets.exceptions.ConnectionClosed:
                    print("Connexion WebSocket fermée par le serveur.")
                    break
    
    except Exception as e:
        print(f"Erreur de connexion WebSocket: {e}")
    finally:
        print("Récepteur de données arrêté.")

async def control_api(action: str):
    """Appelle l'API de contrôle HTTP."""
    url = f"http://{SERVER_URL}/{action}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url)
            print(f"API [POST /{action}]: Réponse {response.status_code} "
                  f"-> {response.json()}")
    except httpx.ConnectError as e:
        print(f"Erreur de connexion API: {e}")

async def main():
    """Scénario de test principal."""
    stop_event = asyncio.Event()

    # Lance le récepteur de données en tâche de fond
    receiver_task = asyncio.create_task(data_receiver(stop_event))
    
    # Laisse au WebSocket le temps de se connecter
    await asyncio.sleep(1)

    # 1. Démarrer l'acquisition
    await control_api("start")

    # 2. Recevoir les données pendant 5 secondes
    print("\n--- Réception des données pendant 5 secondes ---")
    await asyncio.sleep(5)
    print("--- Fin de la réception ---")

    # 3. Arrêter l'acquisition
    await control_api("stop")

    # 4. Arrêter le récepteur de données
    stop_event.set()
    await receiver_task # Attendre que la tâche se termine proprement

    print("\nTest client terminé.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Client interrompu.")