# 🧭 Guide Séquentiel Pas-à-Pas : Défilement des Événements (Étapes 0 à 6)

Ce document retrace **le parcours exact et chronologique** d'un ticket de caisse dans **ExpensyGuard**, de sa prise en photo sur smartphone ou upload web jusqu'à la notification, l'enregistrement de l'image réelle dans `data_images/`, le rattachement au collaborateur et l'exploitation via la **Fiche Employé**.

Chaque étape détaille **le fichier source, la classe utilisée, la méthode appelée, les données entrantes et les données sortantes**.

---

## 🗺️ Schéma Chronologique Global des Événements

```mermaid
flowchart TD
    E0["<b>ÉTAPE 0 : Réception, Enregistrement Image & Initialisation</b><br/>Fichiers: <code>interfaces/telegram_bot.py</code> ou <code>interfaces/api/main.py</code><br/>Action: Sauvegarde physique dans <code>data_images/{receipt_id}.jpg</code><br/>Attribution: <code>employee_id</code>"]
    -->|Données: image_bytes, receipt_id, employee_id| E1["<b>ÉTAPE 1 : Prétraitement & OCR</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/ocr_adapter.py</code><br/>Classe: <code>EasyOCREngine</code> (Port: <code>OCREnginePort</code>)<br/>Méthode: <code>ocr_node()</code> ➔ <code>extract_text()</code>"]
    -->|Données: ocr_raw_text| E2["<b>ÉTAPE 2 : Extraction Structurée par IA</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/llm_adapter.py</code><br/>Classe: <code>OpenAILLMExtractor</code> (Port: <code>LLMExtractorPort</code>)<br/>Méthode: <code>llm_extraction_node()</code> ➔ <code>extract_receipt()</code>"]
    -->|Données: extracted_data (ReceiptExtraction)| E3["<b>ÉTAPE 3 : Contrôle Légal SIRENE</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/registry_api.py</code><br/>Classe: <code>SireneRegistryAPI</code> (Port: <code>RegistryServicePort</code>)<br/>Méthode: <code>registry_validation_node()</code> ➔ <code>verify_merchant()</code>"]
    -->|Données: registry_verification| E4["<b>ÉTAPE 4 : Détection d'Empreinte & Anti-Doublons</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/db_repository.py</code><br/>Classe: <code>SQLiteReceiptRepository</code> (Port: <code>ReceiptRepositoryPort</code>)<br/>Méthode: <code>duplicate_detection_node()</code> ➔ <code>check_duplicate()</code>"]
    -->|Données: duplicate_check (SHA-256)| E5["<b>ÉTAPE 5 : Règles Métier, Décision & Sauvegarde BDD</b><br/>Fichier: <code>application/nodes.py</code> & <code>domain/models.py</code><br/>Classe: <code>AuditDecision</code> & <code>SQLiteReceiptRepository</code><br/>Méthode: <code>business_rules_and_decision_node()</code> ➔ <code>save_audit()</code> (avec <code>employee_id</code> & <code>image_path</code>)"]
    -->|Données: decision (AuditDecision)| E6["<b>ÉTAPE 6 : Restitution, Dashboard & Fiches Collaborateurs</b><br/>Fichiers: <code>interfaces/telegram_bot.py</code> & <code>frontend/src/App.jsx</code><br/>Actions: Notification mobile + Affichage Web + Filtres temporels (Jour, Mois, Année)"]
```

---

## 📋 Déroulé Détaillé Étape par Étape

---

### 🔹 ÉTAPE 0 : Réception, Enregistrement de l'Image Réelle & Initialisation
* **Fichiers concernés :** 
  * Bot Telegram : [src/interfaces/telegram_bot.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/telegram_bot.py)
  * API Web : [src/interfaces/api/main.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/api/main.py)
* **Actions exécutées :**
  1. Génération d'un identifiant unique de reçu `receipt_id` (ex : `rec_1728591234_abc` ou `tg_12345678`).
  2. **Sauvegarde physique de la photo brute** dans le répertoire `data_images/{receipt_id}.jpg`.
  3. Sélection / Assignation de l'identifiant collaborateur `employee_id` (ex: `EMP001`).
* **Ce qui entre :** Le fichier image binaire (upload HTTP ou photo Telegram).
* **Ce qui sort :** `image_bytes: bytes`, `receipt_id: str`, `employee_id: str`, `image_path: str`.
* **Initialisation du flux LangGraph :**
  ```python
  initial_state = {
      "receipt_id": receipt_id,
      "employee_id": employee_id,
      "image_bytes": image_bytes,
      "file_name": f"{receipt_id}.jpg",
      "anomalies": [],
  }
  result = await audit_graph.ainvoke(initial_state)
  ```

---

### 🔹 ÉTAPE 1 : Nœud OCR (Lecture Optique des Pixels)
* **Fichiers :** 
  * Nœud applicatif : [src/application/nodes.py](file:///c:/Tahiri/QRA/expensyguard/src/application/nodes.py#L35)
  * Adaptateur technique : [src/infrastructure/ocr_adapter.py](file:///c:/Tahiri/QRA/expensyguard/src/infrastructure/ocr_adapter.py)
  * Interface : `OCREnginePort` ([src/domain/ports.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/ports.py))
* **Classe :** `EasyOCREngine`
* **Méthodes appelées :**
  1. `ocr_node(state, ocr_engine)` : Fonction de nœud LangGraph.
  2. `_preprocess_image(image_bytes)` : OpenCV applique niveaux de gris, flou gaussien et binarisation adaptative.
  3. `extract_text(image_bytes)` : EasyOCR lit et assemble les lignes de caractères.
* **Ce qui entre :** `state["image_bytes"]`.
* **Ce qui est ajouté au State :**
  ```python
  return {"ocr_raw_text": "BOULANGERIE PAUL\nDATE: 2026-10-07\nTOTAL TTC: 11.00 EUR..."}
  ```

---

### 🔹 ÉTAPE 2 : Nœud LLM (Extraction Structurée par Intelligence Artificielle)
* **Fichiers :** 
  * Nœud applicatif : [src/application/nodes.py](file:///c:/Tahiri/QRA/expensyguard/src/application/nodes.py#L93)
  * Adaptateur technique : [src/infrastructure/llm_adapter.py](file:///c:/Tahiri/QRA/expensyguard/src/infrastructure/llm_adapter.py)
  * Modèle de domaine : `ReceiptExtraction` ([src/domain/models.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/models.py))
  * Interface : `LLMExtractorPort` ([src/domain/ports.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/ports.py))
* **Classe :** `OpenAILLMExtractor`
* **Méthodes appelées :**
  1. `llm_extraction_node(state, llm_extractor)` : Nœud LangGraph.
  2. `extract_receipt(ocr_raw_text)` : Envoie le texte brut au modèle (OpenAI / Gemini) avec prompt d'expertise comptable.
  3. `ReceiptExtraction.model_validate_json(...)` : Pydantic V2 valide les types et montants décimaux.
* **Ce qui entre :** `state["ocr_raw_text"]`.
* **Ce qui est ajouté au State :**
  ```python
  return {
      "extracted_data": ReceiptExtraction(
          merchant=MerchantInfo(name="Paul", siren_or_siret="123456789"),
          date="2026-10-07",
          total_amount_ttc=Decimal("11.00"),
          currency="EUR",
          category=ExpenseCategory.MEAL,
          items=[ReceiptItem(label="Sandwich", total_price=Decimal("11.00"))]
      )
  }
  ```

---

### 🔹 ÉTAPE 3 : Nœud Registre (Vérification Légale SIRENE)
* **Fichiers :** 
  * Nœud applicatif : [src/application/nodes.py](file:///c:/Tahiri/QRA/expensyguard/src/application/nodes.py#L140)
  * Adaptateur technique : [src/infrastructure/registry_api.py](file:///c:/Tahiri/QRA/expensyguard/src/infrastructure/registry_api.py)
  * Interface : `RegistryServicePort` ([src/domain/ports.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/ports.py))
* **Classe :** `SireneRegistryAPI`
* **Méthodes appelées :**
  1. `registry_validation_node(state, registry_service)` : Nœud asynchrone LangGraph.
  2. `verify_merchant(search_term)` : Requête HTTP asynchrone (`httpx.AsyncClient`) vers l'API gouvernementale `recherche-entreprises.api.gouv.fr`.
* **Ce qui entre :** `state["extracted_data"].merchant.name` (ou SIREN).
* **Ce qui est ajouté au State :**
  ```python
  return {
      "registry_verification": {
          "is_found": True,
          "siren": "123456789",
          "nom_complet": "PAUL SAS",
          "is_active": True
      }
  }
  ```

---

### 🔹 ÉTAPE 4 : Nœud Anti-Doublons (Empreinte Cryptographique SHA-256)
* **Fichiers :** 
  * Nœud applicatif : [src/application/nodes.py](file:///c:/Tahiri/QRA/expensyguard/src/application/nodes.py#L197)
  * Adaptateur technique : [src/infrastructure/db_repository.py](file:///c:/Tahiri/QRA/expensyguard/src/infrastructure/db_repository.py)
  * Modèle de domaine : `DuplicateCheckResult` ([src/domain/models.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/models.py))
  * Interface : `ReceiptRepositoryPort` ([src/domain/ports.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/ports.py))
* **Classe :** `SQLiteReceiptRepository`
* **Méthodes appelées :**
  1. `duplicate_detection_node(state, repo)` : Nœud LangGraph.
  2. `compute_fingerprint(merchant, date, amount)` : Calcule le hachage cryptographique `SHA256("paul|2026-10-07|11.00")`.
  3. `check_duplicate(fingerprint)` : Interroge SQLite (`SELECT id FROM receipts WHERE fingerprint = ?`).
* **Ce qui entre :** `merchant`, `date`, `total_amount_ttc`.
* **Ce qui est ajouté au State :**
  ```python
  return {
      "duplicate_check": DuplicateCheckResult(
          is_duplicate=False,
          fingerprint="a8f5c...",
          existing_receipt_id=None
      )
  }
  ```

---

### 🔹 ÉTAPE 5 : Nœud Décision Métier & Sauvegarde Définitive
* **Fichiers :** 
  * Nœud applicatif : [src/application/nodes.py](file:///c:/Tahiri/QRA/expensyguard/src/application/nodes.py#L237)
  * Modèles de domaine : `AuditDecision`, `AuditStatus`, `Anomaly` ([src/domain/models.py](file:///c:/Tahiri/QRA/expensyguard/src/domain/models.py))
  * Adaptateur technique : [src/infrastructure/db_repository.py](file:///c:/Tahiri/QRA/expensyguard/src/infrastructure/db_repository.py)
* **Classes :** `AuditDecision` & `SQLiteReceiptRepository`
* **Méthodes appelées :**
  1. `business_rules_and_decision_node(state, repo, max_meal_expense)` : Nœud LangGraph d'arbitrage.
  2. Application des règles métier :
     * *Vérification du plafond repas :* `if total > 45.00€` ➔ anomalie `WARN_MEAL_CAP_EXCEEDED`.
     * *Cohérence arithmétique :* `if sum(items) != total` ➔ anomalie `WARN_ITEM_TOTAL_MISMATCH`.
  3. Attribution du statut final : `AuditStatus.APPROVED` (ou `FLAGGED_FOR_REVIEW` / `REJECTED`).
  4. `repo.save_audit(receipt_id, fingerprint, extraction, decision, employee_id, image_path)` : Écrit l'enregistrement dans la table SQLite `receipts` liée à `employees`.
* **Ce qui est ajouté au State :**
  ```python
  return {
      "decision": AuditDecision(
          receipt_id="rec_1728591234_abc",
          status=AuditStatus.APPROVED,
          reasons=["Reçu entièrement conforme aux règles."],
          confidence_score=0.99,
          extracted_data=extracted
      )
  }
  ```

---

### 🔹 ÉTAPE 6 : Restitution, Visualisation & Exploitation RH / Comptable
* **Fichiers concernés :** 
  * Bot Telegram : [src/interfaces/telegram_bot.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/telegram_bot.py)
  * API REST : [src/interfaces/api/main.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/api/main.py)
  * Frontend React : [frontend/src/App.jsx](file:///c:/Tahiri/QRA/expensyguard/frontend/src/App.jsx)
* **Exploitation des données :**
  1. **Notification Mobile Telegram :** Message instantané formaté avec badges émojis (🟢 Validé / 🟠 En attente / 🔴 Rejeté).
  2. **Dashboard React :**
     - Tableau en temps réel avec badges de statut et vignette du collaborateur.
     - **Visualisation de l'image :** Bouton ouvrant la photo réelle originale stockée dans `data_images/`.
     - **Fiche Collaborateur Interactive :** Clic sur un collaborateur pour ouvrir sa fiche détaillée (`nom`, `date_embauche`, `date_start`, etc.) avec filtres temporels dynamiques (**Tout**, **Année**, **Mois**, **Jour**) et recalcul instantané des dépenses validées.
     - **Suppression sécurisée :** Action réservée à l'administrateur avec nettoyage simultané de la ligne SQLite et de l'image sur disque.
