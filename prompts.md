## 1. Prompt de génération initiale (Analyse de code vers PRD)

Ce prompt demande à l'IA d'agir comme un **Technical Product Manager (TPM)**. Il est conçu pour extraire la substance logique du code et la formaliser.

> **Rôle :** Agis en tant que Senior Technical Product Manager et Architecte Logiciel.
> **Objectif :** Analyser le code source fourni pour rétro-concevoir un PRD structuré selon la méthode **BMAD**.
> **Instructions d'analyse :**
> 1. **Business (B) :** Identifie la finalité du code. Quels problèmes résout-il ? Qui sont les utilisateurs finaux ? Liste les User Stories implicites.
> 2. **Methods (M) :** Détaille la logique algorithmique. Explique les règles de gestion, les transformations de données et les processus critiques identifiés dans les fonctions.
> 3. **Architecture (A) :** Décris la structure technique. Identifie la stack, les patterns (MVC, microservices, etc.), les modèles de données (schémas SQL/NoSQL), les API et les dépendances externes.
> 4. **Delivery (D) :** Définis les critères d'acceptation (QA), les environnements nécessaires (Docker, CI/CD), et les métriques de performance (KPI) déduites du code.
> 
> 
> **Format de sortie :** Utilise un format Markdown avec des titres de niveau 2 pour chaque section BMAD.
> **Code source à analyser :**
> [COLLER LE CODE ICI]

---

## 2. Prompt d'itération (Ajout de fonctionnalités)

Pour maintenir la cohérence du document lors de l'ajout de fonctions, utilisez ce prompt de mise à jour. Il force l'IA à évaluer l'impact de la nouvelle fonction sur les quatre piliers.

> **Rôle :** Expert en ingénierie logicielle.
> **Contexte :** Nous avons un PRD BMAD existant. Nous devons intégrer une nouvelle fonctionnalité de manière itérative sans briser la structure actuelle.
> **Nouvelle fonctionnalité :** [DÉCRIRE LA FONCTION, ex: "Ajout d'un système de cache Redis pour les requêtes SQL"]
> **Tâches :**
> 1. **Analyse d'impact :** Identifie comment cette fonction modifie les sections existantes.
> 2. **Mise à jour BMAD :**
> * **Business :** Quel est le gain métier de cette itération ?
> * **Methods :** Décris la nouvelle logique ou la modification des algorithmes actuels.
> * **Architecture :** Précise les nouveaux composants techniques ou modifications de schéma.
> * **Delivery :** Ajoute les nouveaux tests unitaires/d'intégration requis et les étapes de déploiement spécifiques.
> 
> 
> 
> 
> **Sortie attendue :** Réécris le PRD complet en intégrant ces modifications de façon transparente (ne pas simplement lister les changements, mais fusionner l'information).

---

## 3. Recommandations techniques pour l'itération

Pour garantir la précision scientifique et technique de vos PRD, je préconise l'application des principes suivants lors de vos interactions :

* **Gestion des Dépendances :** Dans la section **Architecture**, demandez explicitement l'analyse des versions de bibliothèques pour éviter les conflits lors de l'ajout de fonctions (ex: versions de Python, modules C++ ou packages Node.js).
* **Contrôle de Flux :** Pour la section **Methods**, vous pouvez demander un schéma de flux textuel (Mermaid.js) pour visualiser la logique de décision.

[Image d'un diagramme de flux logique logiciel]

### Structure type de la section Architecture (A)

| Composant | Description Technique | Rôle dans le système |
| --- | --- | --- |
| **Data Layer** | PostgreSQL / SQLAlchemy | Persistance des données relationnelles |
| **Logic Layer** | Python Fast API | Gestion des routes et logique métier |
| **Container** | Docker / Docker Compose | Isolation et portabilité de l'environnement |





 --------------------------- Prompt de génération de test unitaire ---------------------------


1. Prompt Structuré (à copier-coller)

    Rôle : Agis en tant qu'Ingénieur Senior QA et Expert DevOps.

    Contexte : Je possède un projet Fullstack composé d'un backend en FastAPI (API REST) + Uvicorn (Serveur ASIC). Bibliothèque `pynq` (Overlay, Allocate, DMA) et d'un frontend wxPython

    Tâche : Configure un environnement de test complet utilisant Pytest. La solution doit couvrir :

        Tests Unitaires et d'Intégration pour le backend.

        Tests End-to-End (E2E) pour valider le flux complet (Frontend + Backend) en utilisant le plugin pytest-playwright ou pytest-selenium.

    Contraintes Techniques :

        Fixtures : Crée un fichier conftest.py incluant des fixtures pour l'initialisation de la base de données de test, le client API, et l'authentification.

        Mocking : Utilise pytest-mock pour isoler les services tiers.

        Docker : Fournis une configuration docker-compose.test.yml pour exécuter les tests dans un environnement isolé.

        Qualité : Inclus le calcul de couverture de code avec pytest-cov.

        Parallélisation : Configure pytest-xdist pour accélérer l'exécution.

    Format de réponse attendu :

        Arborescence du répertoire /tests.

        Contenu des fichiers de configuration (pytest.ini, conftest.py).

        Un exemple de test d'intégration API

        Un exemple de test E2E simulant un utilisateur sur le frontend.

        Commandes CLI pour l'exécution (script shell)