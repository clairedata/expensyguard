# ExpensyGuard 🛡️ - Audit Automatisé de Reçus Fiscaux

ExpensyGuard est un système d'audit automatique et intelligent de notes de frais et de reçus de caisse basé sur les principes de la **Clean Architecture (Architecture Hexagonale)** et orchestré par une machine d'états **LangGraph**.

---

## 🏛️ Architecture du Projet

```text
expensyguard/
├── .env                      # Variables d'environnement locales (Tokens, API Keys)
├── .env.example              # Exemple de configuration
├── pyproject.toml            # Dépendances et métadonnées du projet
├── README.md                 # Documentation
├── plan_projet.md            # Spécifications et blueprint technique
├── src/
│   ├── __init__.py
│   ├── domain/               # Cœur métier (Pur, sans dépendances I/O)
│   │   ├── __init__.py
│   │   ├── models.py         # Entités, Value Objects (Pydantic V2 + Decimal)
│   │   └── ports.py          # Contrats d'interfaces abstraites (ABC)
│   ├── infrastructure/       # Adaptateurs d'infrastructure (I/O, APIs, BDD)
│   │   ├── __init__.py
│   │   ├── ocr_adapter.py    # Prétraitement OpenCV + Reconnaissance EasyOCR
│   │   ├── llm_adapter.py    # Extraction structurée via OpenAI / Ollama
│   │   ├── registry_api.py   # Client httpx asynchrone (API Recherche Entreprises)
│   │   └── db_repository.py  # SQLite avec détection d'empreintes SHA-256
│   ├── application/          # Orchestration des cas d'usage & Graphe d'états
│   │   ├── __init__.py
│   │   ├── state.py          # Schéma de l'état AuditFlowState
│   │   ├── nodes.py          # Nœuds atomiques et isolés du graphe
│   │   └── graph.py          # Assemblage du workflow StateGraph LangGraph
│   └── interfaces/           # Points d'entrée (Bot Telegram, CLI & API)
│       ├── __init__.py
│       ├── telegram_bot.py   # 📱 Bot Telegram (Réception photo mobile & réponse en direct)
│       ├── cli.py            # Commande CLI pour tester une image locale
│       └── api/
│           ├── __init__.py
│           └── main.py       # API REST FastAPI (Endpoint d'upload & audit)
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── __init__.py
    │   └── test_domain_models.py
    └── integration/
        ├── __init__.py
        └── test_full_pipeline.py
```

---

## 🚀 Commandes d'Exécution (à exécuter manuellement)

### 1. Démarrer le Bot Telegram (Réception Mobile en Direct)
```bash
uv run python -m src.interfaces.telegram_bot
```
> Ouvrez votre application Telegram sur votre smartphone, envoyez une photo de votre ticket de caisse à votre bot, et recevez l'audit instantanément !

### 2. Lancement de l'API FastAPI
```bash
uv run uvicorn src.interfaces.api.main:app --reload --port 8000
```
* Accès à la documentation interactive Swagger : `http://localhost:8000/docs`

### 3. Exécution du CLI sur une image de test
```bash
uv run python -m src.interfaces.cli --image "chemin/vers/votre_recu.jpg" --max-meal 45.00
```

### 4. Exécution de la suite de tests
```bash
uv run pytest -v
```
