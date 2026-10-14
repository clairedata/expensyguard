# Guide Technique & Architecture : Intégration du Bot Telegram

Ce document détaille le fonctionnement complet de l'intégration entre **Telegram** et **ExpensyGuard**, le rôle de chaque bloc de code dans [src/interfaces/telegram_bot.py](file:///c:/Tahiri/QRA/expensyguard/src/interfaces/telegram_bot.py), la sauvegarde des images réelles dans `data_images/`, et les raisons architecturales de cette conception.

---

## 🏛️ 1. Pourquoi cette Architecture ?

Dans une **Clean Architecture (Architecture Hexagonale)**, le Bot Telegram est placé dans le dossier **`src/interfaces/`** :

```text
expensyguard/
├── data_images/          # Stockage des photos réelles de tickets transmises par Telegram
├── src/
│   ├── domain/           # 1. Règles comptables, Modèles de données purs & Collaborateurs
│   ├── infrastructure/   # 2. Outils techniques (OpenCV, SQLite, OpenAI, SIRENE, Sécurité)
│   ├── application/      # 3. Graphe d'états LangGraph (Le Chef d'Orchestre)
│   └── interfaces/       # 4. Points d'Entrée & Sortie (CLI, API FastAPI, Bot Telegram)
│       └── telegram_bot.py
```

### Les 4 Bénéfices de ce choix :

1. **Indépendance Totale (Découplage) :** 
   Le moteur d'audit (OCR, LLM, base de données) ne dépend pas de Telegram. Pour le moteur, Telegram est un adaptateur d'entrée fournissant des octets d'images, identique à l'API FastAPI ou la CLI.
2. **Interchangeabilité & Omnicanalité :** 
   Les reçus envoyés par Telegram s'intègrent automatiquement au même référentiel SQLite et au même dossier `data_images/` que ceux envoyés par l'interface Web React.
3. **Zéro Dépendance Lourde Supplémentaire :** 
   Au lieu d'utiliser des bibliothèques externes complexes, nous utilisons directement le client HTTP asynchrone **`httpx`** (déjà présent dans le projet). Le code reste léger, performant et transparent.
4. **Mode Long-Polling Asynchrone :** 
   Permet au bot d'écouter les messages en local **sans ouvrir de ports réseaux ni nécessiter de tunnels type ngrok**.

---

## 🔄 2. Schéma du Flux de Données Telegram

```mermaid
sequenceDiagram
    autonumber
    actor User as 📱 Collaborateur (Telegram)
    participant TG as ☁️ Serveurs Telegram
    participant Bot as 🤖 telegram_bot.py (Interface)
    participant FS as 📁 data_images/ (Disque)
    participant Graph as ⚙️ graph.py (LangGraph)
    participant DB as 💾 SQLite (expensyguard.db)

    User->>TG: Envoie la photo d'un ticket de caisse
    Bot->>TG: getUpdates (Long-Polling via httpx)
    TG-->>Bot: Transmet le message + file_id
    Bot->>TG: sendMessage ("⏳ Analyse en cours...")
    Bot->>TG: getFile + Téléchargement de la photo brute
    Bot->>FS: Sauvegarde physique dans data_images/{receipt_id}.jpg
    Bot->>Graph: ainvoke({"image_bytes": ..., "receipt_id": ..., "employee_id": ...})

    Note over Graph: 
    1. OCR (OpenCV + EasyOCR)<br/>
    2. LLM (Extraction Pydantic)<br/>
    3. Registre SIRENE<br/>4. Anti-Doublons SHA-256

    Graph->>DB: Sauvegarde la décision, l'audit & le chemin de l'image
    Graph-->>Bot: Retourne l'objet AuditDecision
    Bot->>Bot: Formate le message avec badges émojis (🟢/🟠/🔴)
    Bot->>TG: sendMessage (Rapport d'audit complet)
    TG-->>User: Affiche le résultat d'audit sur le smartphone
```

---

## 🔍 3. Explication Détaillée du Code (`telegram_bot.py`)

---

### A. Téléchargement & Sauvegarde de la Photo Réelle (`download_photo`)
```python
async def download_photo(self, client: httpx.AsyncClient, file_id: str) -> bytes:
    # 1. Requête de localisation du fichier sur les serveurs Telegram
    get_file_url = f"{self.api_url}/getFile"
    response = await client.get(get_file_url, params={"file_id": file_id})
    file_path = response.json()["result"]["file_path"]
    
    # 2. Téléchargement direct du flux d'octets binaires
    download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
    img_response = await client.get(download_url)
    return img_response.content
```
* Le bot télécharge l'image originale brute en pleine résolution.
* Dans `process_update()`, cette image est immédiatement stockée sur le disque dans le dossier `data_images/{receipt_id}.jpg` :
  ```python
  image_dir = Path("data_images")
  image_dir.mkdir(exist_ok=True)
  local_path = image_dir / f"{receipt_id}.jpg"
  local_path.write_bytes(image_bytes)
  ```
* Cela garantit que la photo réelle peut être visualisée à tout moment sur le **Dashboard Web React**.

---

### B. L'Exécution de l'Audit & Formatage du Rapport
```python
state = {
    "receipt_id": receipt_id,
    "employee_id": "EMP001",  # Collaborateur par défaut ou associé au compte Telegram
    "image_bytes": image_bytes,
    "file_name": f"{receipt_id}.jpg",
    "anomalies": [],
}
result = await self.audit_graph.ainvoke(state)
decision = result.get("decision")
```
* Le graphe LangGraph effectue les contrôles (OCR, Extraction LLM, SIRENE, Empreinte SHA-256).
* `format_audit_message()` génère un rapport lisible avec émojis :
  * 🟢 **REÇU CONFORME ET VALIDÉ** (Dépense prise en compte dans le total d'entreprise)
  * 🟠 **REÇU EN ATTENTE DE VÉRIFICATION**
  * 🔴 **REÇU NON CONFORME / REJETÉ**
