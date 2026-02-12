# Product Requirement Document (PRD) - PYNQ Scope

### Finalité
Le projet **PYNQ Scope** a pour objectif de fournir une solution d'oscilloscope numérique légère et accessible via le réseau pour les plateformes FPGA PYNQ (Xilinx Zynq). Il permet la visualisation en temps réel de signaux internes du FPGA sans nécessiter d'équipement de mesure externe coûteux ou de sondes physiques complexes.

### Problèmes résolus
*   **Complexité du débogage FPGA** : Facilite l'accès aux signaux internes sans utiliser un ILA (Integrated Logic Analyzer) lourd ou des sorties I/O physiques limitées.
*   **Accès à distance** : Permet de surveiller et contrôler l'acquisition de données à distance via une architecture client-serveur.


### User Stories Implicites
*   **Visualisation** : En tant qu'utilisateur, je veux visualiser en temps réel les formes d'onde de 8 inputs distincts
*   **Contrôle** : En tant qu'utilisateur, je veux démarrer et arrêter l'acquisition à la demande.
*   **Configuration** : En tant qu'utilisateur, je veux modifier la fréquence d'échantillonnage et configurer le mode d'acquisition (Continu ou Durée Fixe).
*   **Export** : En tant qu'utilisateur, je veux enregistrer les données acquises dans un fichier CSV pour une analyse post-traitement.
*   **Connectivité** : En tant qu'utilisateur, je veux me connecter au serveur via son adresse IP pour visualiser les données depuis mon poste de travail.


### Logique Algorithmique & Processus
1.  **Acquisition de Données (Server-side)** :
    *   **Mode Réel (Hardware)** : Utilise le module `dma_acquisition`. Le système charge un bitstream FPGA (`activ_filter_one_7010.bit`) et configure un bloc IP `axi_dma` pour transférer les données de la logique programmable (PL) vers la mémoire du processeur (PS).
    *   **Mode Émulation** : Génère synthétiquement des ondes sinusoïdales sur 8 canaux avec des fréquences variables pour simuler des données réelles sans matériel FPGA.
    *   **Boucle d'Acquisition** : Une tâche `asyncio` (`_acquisition_loop`) récupère les données par blocs (`CHUNK_SIZE`), soit via un `ThreadPoolExecutor` pour l'appel bloquant DMA, soit par calcul direct en émulation.

2.  **Traitement des Données** :
    *   **Démultiplexage** : Les données brutes entrelacées provenant du DMA sont séparées en 8 tableaux `numpy` distincts (Canal 0 à 7).
    *   **Mise en mémoire tampon** :
        *   **Mode Auto** : Utilise une `deque` circulaire pour garder un historique glissant (ex: dernière minute).
        *   **Mode Timed** : Accumule toutes les données dans une liste jusqu'à la fin de la durée spécifiée.

3.  **Gestion des Actions** :
    *   Le serveur utilise un `AcquisitionManager` pour dispatcher les commandes (`start`, `stop`, `handle_action`).
    *   Configuration dynamique (ex: changement de `SAMPLE_RATE`) via endpoint REST.

## Architecture (A)

### Structure Technique
L'application suit une architecture **Client-Serveur** découplée.

### Stack Technologique
*   **Serveur (Backend)** :
    *   **Langage** : Python 3.
    *   **Web Framework** : FastAPI (API REST) + Uvicorn (Serveur ASIC).
    *   **Hardware Interface** : Bibliothèque `pynq` (Overlay, Allocate, DMA).
    *   **Calcul** : `numpy` pour la manipulation performante des buffers.
    *   **Communication** : WebSockets pour le streaming de données temps-réel.
*   **Client (Frontend/GUI)** :
    *   **Framework GUI** : `wxPython`.
    *   **Visualisation** : `matplotlib` (Backend `WXAgg`).
    *   **Réseau** : `httpx` (Requêtes REST) et `websockets` (Flux de données).

### Patterns & Modèles
*   **Async/Await (Concurrency)** : Utilisation extensive de `asyncio` sur le serveur et le client pour gérer les I/O réseau sans bloquer l'interface ou l'acquisition.
*   **Producer-Consumer** :
    *   *Producteur* : Le thread/tâche d'acquisition qui remplit le buffer.
    *   *Consommateur* : La méthode `broadcast` qui envoie les données aux clients WebSocket.
*   **Models de Données** :
    *   Données transitoires : Flux binaire (`int16`).
    *   Persistance : Fichiers plats (CSV) générés sur demande côté serveur.

### Interfaces (API)
*   **REST (Control Plane)** :
    *   `POST /start` : Démarre l'acquisition (params: mode, duration).
    *   `POST /stop` : Arrête l'acquisition.
    *   `POST /configure` : Actions génériques (ex: `set_sample_rate`, `save_to_csv`).
    *   `GET /status` : État du serveur (running, nombre de clients).
*   **WebSocket (Data Plane)** :
    *   `WS /ws/data` : Flux unidirectionnel (Serveur -> Client) de données binaires.

## Delivery (D)

### Critères d'Acceptation (QA)
1.  **Stabilité** : Le serveur ne doit pas crasher si le client se déconnecte brutalement (gestion des exceptions `WebSocketDisconnect`).
2.  **Intégrité des Données** : Les données enregistrées dans le CSV doivent correspondre aux signaux visualisés (vérifiable via les sinusoides en mode émulation).
3.  **Portabilité** : Le client GUI doit pouvoir s'exécuter sur n'importe quel OS supportant Python/wxPython, tandis que le serveur tourne sur Linux (PYNQ).
4.  **Tests** : Passage complet de la suite de tests unitaires (`pytest`) couvrant les endpoints API et la logique du Manager.

### Environnements Nécessaires
*   **Développement / CI** :
    *   Environnement Python standard.
    *   Mode `--emulate` pour valider la logique sans accès au FPGA.
    *   Bibliothèques mockées (`sys.modules['pynq'] = MagicMock()`).
*   **Production (Target)** :
    *   Carte compatible Xilinx PYNQ (ex: PYNQ-Z1, Z2, Ultra96).
    *   Accès root pour le chargement des bitstreams (PL).
    *   Dépendances : `pynq`, `numpy`, `fastapi`, `uvicorn`.

### Métriques de Performance (KPI)
*   **Taux de Rafraîchissement** : Calculé et affiché par le GUI (Hz). Doit être suffisant pour une fluidité visuelle (> 20 Hz).
*   **Bande Passante** : débit de données transféré (kB/s).
*   **Latence** : Délai entre l'acquisition DMA et l'affichage (critique pour le temps réel).
*   **Usage Mémoire** : Pour le mode "Auto", limitation de la taille de la `deque` pour éviter les OOM (Out Of Memory) sur la carte embarquée.
