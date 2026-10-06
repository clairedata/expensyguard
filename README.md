# 🛡️ ExpensyGuard - Audit Automatisé de Reçus Fiscaux

[![Python 3.13](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![Architecture Hexagonale](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonale-brightgreen.svg)](https://martinfowler.com/bliki/HexagonalArchitecture.html)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20100%25-success.svg)](https://docs.pytest.org/)

**ExpensyGuard** est un système d'audit automatique et intelligent de notes de frais et de reçus de caisse. Il permet aux collaborateurs d'envoyer des photos de tickets (via smartphone/Telegram), applique un prétraitement optique (OCR), extrait les données financières par IA, valide la légalité du commerçant (API SIRENE), et bloque les doublons en base SQL.

---

## 🏛️ Architecture Hexagonale avec Rôles & Actions Verbeuses

Chaque couche a une responsabilité unique et précise, exprimée par des verbes d'action :

```mermaid
flowchart TB
    subgraph Interfaces["🚪 1. INTERFACES (Points d'Entrée & Sortie)"]
        direction TB
        TG["📱 Bot Telegram<br/><b>Action :</b> Réceptionne la photo mobile & répond"]
        API["🌐 FastAPI REST<br/><b>Action :</b> Expose les endpoints HTTP & uploads"]
        CLI["💻 Terminal CLI<br/><b>Action :</b> Exécute un test unitaire en console"]
    end

    subgraph Application["⚙️ 2. APPLICATION (Orchestrateur LangGraph)"]
        direction TB
        Graph["🧠 Machine d'États LangGraph<br/><b>Actions principales :</b><br/>• <i>Orchestre</i> le flux séquentiel des nœuds<br/>• <i>Transmet</i> la mémoire partagée (State)<br/>• <i>Applique</i> les seuils de dépenses (Plafond repas 45€)<br/>• <i>Arbitre</i> la décision finale (APPROVED / REJECTED)"]
    end

    subgraph Domain["💎 3. DOMAINE MÉTIER (Cœur Pur & Invariable)"]
        direction TB
        Models["📦 Entités Pydantic V2<br/><b>Action :</b> <i>Définit</i> et <i>Valide</i> la structure des données pures"]
        Ports["🔌 Interfaces Abstraites (Ports)<br/><b>Action :</b> <i>Impose</i> les contrats stricts aux outils externes"]
    end

    subgraph Infrastructure["🛠️ 4. INFRASTRUCTURE (Adaptateurs & Outils Techniques)"]
        direction TB
        OCR["👁️ OpenCV + EasyOCR<br/><b>Action :</b> <i>Prétraite</i> l'image et <i>Lit</i> les pixels de texte"]
        LLM["🤖 OpenAI / Gemini<br/><b>Action :</b> <i>Transforme</i> le texte brut en données JSON typées"]
        REG["🏛️ API SIRENE (Gouv)<br/><b>Action :</b> <i>Vérifie</i> l'existence légale de l'entreprise"]
        DB["💾 SQLite Repository<br/><b>Action :</b> <i>Calcule</i> l'empreinte SHA-256 et <i>Bloque</i> les doublons"]
    end

    %% Relations avec verbes d'action
    Interfaces -->|📥 Transmet le fichier brut| Application
    Application -->|📐 Utilise les règles & types| Domain
    Infrastructure -.->|🤝 Respecte les contrats| Ports
    Application -->|⚡ Déclenche les adaptateurs| Infrastructure
```

---

## 🔄 Flux Séquentiel d'un Reçu (Workflow d'Audit)

Le parcours étape par étape avec les actions effectuées à chaque maillon de la chaîne :

```mermaid
sequenceDiagram
    autonumber
    actor Employe as 📱 Employé (Mobile)
    participant Bot as 🤖 Interface Telegram
    participant LangGraph as ⚙️ Orchestrateur
    participant OCR as 👁️ OpenCV / EasyOCR
    participant LLM as 🧠 Moteur IA (LLM)
    participant SIRENE as 🏛️ Registre Légal
    participant SQLite as 💾 Base de Données

    Employe->>Bot: 1. 📤 Envoie la photo du ticket
    Bot->>LangGraph: 2. 🚀 Initialise le flux avec l'image binaire
    LangGraph->>OCR: 3. 🔍 Prétraite l'image & Extrait le texte brut
    OCR-->>LangGraph: 4. 📄 Retourne le texte brut
    LangGraph->>LLM: 5. 🧩 Parse & Structure en JSON (Montants, TVA, Date)
    LLM-->>LangGraph: 6. 📊 Retourne l'objet ReceiptExtraction
    LangGraph->>SIRENE: 7. 🔎 Vérifie le SIREN / Nom du commerçant
    SIRENE-->>LangGraph: 8. ✅ Confirme l'activité légale de l'entreprise
    LangGraph->>SQLite: 9. 🔐 Calcule l'empreinte SHA-256 & Détecte les doublons
    SQLite-->>LangGraph: 10. 🛡️ Confirme l'absence de doublon
    LangGraph->>LangGraph: 11. ⚖️ Évalue le respect du plafond (45€ repas)
    LangGraph->>SQLite: 12. 💾 Enregistre la décision définitive
    LangGraph-->>Bot: 13. 📦 Émet l'objet AuditDecision final
    Bot-->>Employe: 14. 🟢 Envoie le rapport de validation instantané
```

---

## 📁 Arborescence du Projet

```text
expensyguard/
├── .env.example              # Gabarit des variables de configuration
├── README.md                 # Présentation & documentation du projet
├── connexion_to_bot.md       # Guide détaillé de l'intégration Telegram
├── plan_projet.md            # Spécifications et blueprint technique
├── pyproject.toml            # Dépendances du projet (uv)
├── src/
│   ├── __init__.py
│   ├── domain/               # 💎 Cœur Métier Pur (Sans I/O)
│   │   ├── __init__.py
│   │   ├── models.py         # Entités Pydantic V2 & Decimal (Receipt, Tax, Status)
│   │   └── ports.py          # Interfaces abstraites (Contrats hexagonaux)
│   ├── infrastructure/       # 🛠️ Adaptateurs Techniques (I/O, APIs, BDD)
│   │   ├── __init__.py
│   │   ├── ocr_adapter.py    # Prétraitement OpenCV + Reconnaissance EasyOCR
│   │   ├── llm_adapter.py    # Client OpenAI / Google Gemini
│   │   ├── registry_api.py   # Client HTTP asynchrone (API Entreprises SIRENE)
│   │   └── db_repository.py  # SQLite & détection de doublons (SHA-256)
│   ├── application/          # ⚙️ Orchestration des Cas d'Usage
│   │   ├── __init__.py
│   │   ├── state.py          # État partagé du graphe (AuditFlowState)
│   │   ├── nodes.py          # Nœuds atomiques de décision et d'audit
│   │   └── graph.py          # Assemblage StateGraph & compilation LangGraph
│   └── interfaces/           # 🚪 Points d'Entrée Utilisateurs
│       ├── __init__.py
│       ├── telegram_bot.py   # Bot Telegram (Réception photo mobile & réponse direct)
│       ├── cli.py            # Commande CLI locale
│       └── api/              # API REST FastAPI
│           ├── __init__.py
│           └── main.py
└── tests/
    ├── __init__.py
    ├── unit/                 # Tests unitaires des modèles et de la validation
    │   ├── __init__.py
    │   └── test_domain_models.py
    └── integration/          # Tests d'intégration du graphe LangGraph complet
        ├── __init__.py
        └── test_full_pipeline.py
```

---

## 🚀 Guide de Démarrage Rapide

### 1. Installation des dépendances
```bash
uv sync
```

### 2. Configuration (`.env`)
Copiez le fichier exemple et renseignez vos clés :
```bash
cp .env.example .env
```

### 3. Exécution des Tests Automatisés
```bash
uv run pytest -v
```

### 4. Lancer le Bot Telegram
```bash
uv run python -m src.interfaces.telegram_bot
```

### 5. Lancer l'API REST FastAPI
```bash
uv run uvicorn src.interfaces.api.main:app --reload --port 8000
```
> *Documentation Swagger disponible sur : `http://localhost:8000/docs`*
