# 🧭 Guide Séquentiel Pas-à-Pas : Défilement des Événements (Étapes 0 à 6)

Ce document retrace **le parcours exact et chronologique** d'un ticket de caisse dans **ExpensyGuard**, de sa prise en photo sur smartphone jusqu'à la notification finale.

Chaque étape détaille **le fichier source, la classe utilisée, la méthode appelée, les données entrantes et les données sortantes**.

---

## 🗺️ Schéma Chronologique Global des Événements

```mermaid
flowchart TD
    E0["<b>ÉTAPE 0 : Réception & Téléchargement</b><br/>Fichier: <code>interfaces/telegram_bot.py</code><br/>Classe: <code>TelegramReceiptBot</code><br/>Méthode: <code>download_photo()</code>"]
    -->|Données: image_bytes| E1["<b>ÉTAPE 1 : Prétraitement & OCR</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/ocr_adapter.py</code><br/>Classe: <code>EasyOCREngine</code> (Port: <code>OCREnginePort</code>)<br/>Méthode: <code>ocr_node()</code> ➔ <code>extract_text()</code>"]
    -->|Données: ocr_raw_text| E2["<b>ÉTAPE 2 : Extraction Structurée par IA</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/llm_adapter.py</code><br/>Classe: <code>OpenAILLMExtractor</code> (Port: <code>LLMExtractorPort</code>)<br/>Méthode: <code>llm_extraction_node()</code> ➔ <code>extract_receipt()</code>"]
    -->|Données: extracted_data (ReceiptExtraction)| E3["<b>ÉTAPE 3 : Contrôle Légal SIRENE</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/registry_api.py</code><br/>Classe: <code>SireneRegistryAPI</code> (Port: <code>RegistryServicePort</code>)<br/>Méthode: <code>registry_validation_node()</code> ➔ <code>verify_merchant()</code>"]
    -->|Données: registry_verification| E4["<b>ÉTAPE 4 : Détection d'Empreinte & Anti-Doublons</b><br/>Fichier: <code>application/nodes.py</code> & <code>infrastructure/db_repository.py</code><br/>Classe: <code>SQLiteReceiptRepository</code> (Port: <code>ReceiptRepositoryPort</code>)<br/>Méthode: <code>duplicate_detection_node()</code> ➔ <code>check_duplicate()</code>"]
    -->|Données: duplicate_check (SHA-256)| E5["<b>ÉTAPE 5 : Règles Métier, Décision & Sauvegarde</b><br/>Fichier: <code>application/nodes.py</code> & <code>domain/models.py</code><br/>Classe: <code>AuditDecision</code> & <code>SQLiteReceiptRepository</code><br/>Méthode: <code>business_rules_and_decision_node()</code> ➔ <code>save_audit()</code>"]
    -->|Données: decision (AuditDecision)| E6["<b>ÉTAPE 6 : Restitution & Notification Mobile</b><br/>Fichier: <code>interfaces/telegram_bot.py</code><br/>Classe: <code>TelegramReceiptBot</code><br/>Méthode: <code>format_audit_message()</code> ➔ <code>send_message()</code>"]
```

---

## 📋 Déroulé Détaillé Étape par Étape

---

### 🔹 ÉTAPE 0 : Réception du Message & Téléchargement Mobile
* **Fichier :** [src/interfaces/telegram_bot.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/telegram_bot.py)
* **Classe :** `TelegramReceiptBot`
* **Méthodes appelées :**
  1. `run_polling()` : Boucle asynchrone qui attend les nouveaux messages (`client.get("/getUpdates")`).
  2. `process_update()` : Détecte si le message contient une photo.
  3. `download_photo(client, file_id)` : Télécharge le fichier image binaire depuis les serveurs Telegram.
* **Ce qui entre :** Le message Telegram contenant `file_id`.
* **Ce qui sort :** `image_bytes: bytes` (la photo du reçu en mémoire RAM).
* **Déclenchement du moteur :**
  ```python
  # Initialisation du State et appel du graphe LangGraph :
  initial_state = {
      "receipt_id": "tg_12345678",
      "image_bytes": image_bytes,
      "file_name": "receipt.jpg",
      "anomalies": [],
  }
  result = await self.audit_graph.ainvoke(initial_state)
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
  # Objet ReceiptExtraction typé :
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

### 🔹 ÉTAPE 4 : Nœud Anti-Doublons (Empreinte SHA-256 & BDD)
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
  4. `repo.save_audit(receipt_id, fingerprint, extraction, decision)` : Écrit l'enregistrement dans la table SQLite `receipts` (fichier `expensyguard.db`).
* **Ce qui entre :** Toutes les données accumulées dans `AuditFlowState`.
* **Ce qui est ajouté au State :**
  ```python
  return {
      "decision": AuditDecision(
          receipt_id="tg_12345678",
          status=AuditStatus.APPROVED,
          reasons=["Reçu entièrement conforme aux règles."],
          confidence_score=0.99,
          extracted_data=extracted
      )
  }
  ```

---

### 🔹 ÉTAPE 6 : Restitution & Notification Mobile (Fin de chaîne)
* **Fichier :** [src/interfaces/telegram_bot.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/telegram_bot.py)
* **Classe :** `TelegramReceiptBot`
* **Méthodes appelées :**
  1. `format_audit_message(decision)` : Génère le texte formaté avec badges émojis (🟢 Vert / 🟠 Orange / 🔴 Rouge).
  2. `send_message(client, chat_id, text)` : Requête HTTP `POST /sendMessage` vers l'API Telegram.
* **Ce qui entre :** L'objet final `decision: AuditDecision`.
* **Ce qui sort sur le smartphone :**
  > 🟢 **REÇU CONFORME ET VALIDÉ**
  > 🏢 **Commerçant :** Paul  
  > 📅 **Date :** 2026-10-07  
  > 💶 **Montant TTC :** 11.00 EUR  
  > 🏛️ **Registre SIRENE :** Entreprise active ✅  
  > 🆔 `tg_12345678`
