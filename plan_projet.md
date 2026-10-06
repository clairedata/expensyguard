# Blueprint Technique : ExpensyGuard (Audit Automatisé de Reçus)

## 1. Contexte & Objectif du Projet
Construire un système d'audit automatique de notes de frais et reçus fiscaux en **Clean Architecture (Hexagonale)**.
Le système reçoit une image/PDF de reçu de caisse, applique un prétraitement et un OCR, utilise un LLM pour extraire les données au format JSON structuré et typé, valide l'existence légale du commerçant via une API publique de registre (SIRENE), bloque les doublons en base SQL, et orchestre la décision finale via une machine d'états **LangGraph**.

---

## 2. Stack Technique & Dépendances
* **Python :** >= 3.11
* **Gestionnaire de dépendances :** `uv` ou `pip`
* **Validation & Typage :** Pydantic V2 (`BaseModel`, `Field`, `model_validator`) + `decimal.Decimal`
* **OCR & Vision :** `opencv-python-headless`, `easyocr`, `Pillow`
* **LLM & Extraction :** `openai` (Structured Outputs via `client.beta.chat.completions.parse` compatible OpenAI/Ollama)
* **Client Réseau :** `httpx` (asynchrone)
* **Orchestration Agentique :** `langgraph`
* **Base de données :** `sqlite3` (fichier local ou in-memory)
* **Interface HTTP :** `fastapi`, `uvicorn`, `python-multipart`
* **Tests :** `pytest`, `pytest-asyncio`

---

## 3. Arborescence du Projet

```text
expensyguard/
├── .env.example
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py         # Entités, Enums, Value Objects (Pydantic V2 + Decimal)
│   │   └── ports.py          # Interfaces abstraites (OCR, LLM, Registre, DB)
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── ocr_adapter.py    # Implémentation OpenCV + EasyOCR
│   │   ├── llm_adapter.py    # Client OpenAI/Ollama avec Structured Outputs
│   │   ├── registry_api.py   # Client httpx asynchrone (API Recherche Entreprises)
│   │   └── db_repository.py  # SQLite avec détection d'empreinte unique
│   ├── application/
│   │   ├── __init__.py
│   │   ├── state.py          # TypedDict AuditFlowState pour LangGraph
│   │   ├── nodes.py          # Nœuds atomiques du graphe
│   │   └── graph.py          # Assemblage StateGraph & compilation
│   └── interfaces/
│       ├── __init__.py
│       ├── cli.py            # Commande CLI pour tester une image
│       └── api/
│           ├── __init__.py
│           └── main.py       # API FastAPI (Upload & Audit)
└── tests/
    ├── __init__.py
    ├── unit/
    │   └── test_domain_models.py
    └── integration/
        └── test_full_pipeline.py