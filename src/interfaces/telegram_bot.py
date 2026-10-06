# ==============================================================================
# INTERFACE BOT TELEGRAM (src/interfaces/telegram_bot.py)
# Réception de photos de tickets de caisse et audit automatique en temps réel
# ==============================================================================

# Importation du module asyncio pour exécuter la boucle asynchrone d'écoute
import asyncio

# Importation du module standard de gestion des variables d'environnement
import os

# Importation du module pathlib pour localiser précisément le fichier .env
from pathlib import Path

# Importation du module UUID pour attribuer un identifiant unique à chaque audit
import uuid

# Importation du module Decimal pour la précision des règles de dépenses
from decimal import Decimal

# Importation des types pour annoter les fonctions
from typing import Any, Dict, Optional

# Importation du client HTTP asynchrone httpx
import httpx

# Importation relative du constructeur de graphe d'audit LangGraph
from ..application.graph import build_audit_graph

# Importation relative des modèles de domaine et statuts
from ..domain.models import AuditDecision, AuditStatus

# Importation relative des adaptateurs d'infrastructure
from ..infrastructure.db_repository import SQLiteReceiptRepository
from ..infrastructure.llm_adapter import OpenAILLMExtractor
from ..infrastructure.ocr_adapter import EasyOCREngine
from ..infrastructure.registry_api import SireneRegistryAPI


# Fonction utilitaire pour charger automatiquement les variables du fichier .env
def load_dotenv_custom(env_path: Optional[str] = None) -> None:
    # Détermination du chemin du fichier .env à la racine du projet
    path_to_env = Path(env_path) if env_path else Path(__file__).resolve().parent.parent.parent / ".env"
    # Vérification si le fichier .env existe bien sur le disque
    if path_to_env.exists():
        # Lecture du fichier ligne par ligne
        with open(path_to_env, "r", encoding="utf-8") as file_handle:
            # Parcours de chaque ligne
            for line in file_handle:
                # Nettoyage des espaces et retours chariot
                cleaned_line = line.strip()
                # Ignorer les lignes vides et les commentaires
                if cleaned_line and not cleaned_line.startswith("#") and "=" in cleaned_line:
                    # Découpage sur le premier signe égal
                    key, value = cleaned_line.split("=", 1)
                    # Nettoyage de la clé
                    key = key.strip()
                    # Nettoyage de la valeur en retirant les guillemets éventuels
                    value = value.strip().strip('"').strip("'")
                    # Injection dans os.environ
                    os.environ[key] = value


# Classe gérant les interactions asynchrones avec l'API Telegram
class TelegramReceiptBot:
    # Constructeur initialisant le token et le graphe d'audit
    def __init__(self, token: Optional[str] = None):
        # Chargement automatique des variables d'environnement depuis .env
        load_dotenv_custom()
        # Récupération du token du bot depuis les paramètres ou l'environnement
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        # Vérification si le token est manquant ou non renseigné
        if not self.token or self.token == "votre_token_telegram_ici":
            # Message d'erreur explicite
            raise ValueError(
                "Le jeton TELEGRAM_BOT_TOKEN est manquant dans le fichier .env."
            )
        # Construction de l'URL de base pour les appels à l'API Telegram
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        # Décalage d'index pour ne pas relire les anciens messages (offset)
        self.offset = 0

        # Instanciation de l'adaptateur OCR OpenCV + EasyOCR
        self.ocr_adapter = EasyOCREngine()
        # Instanciation de l'adaptateur LLM OpenAI
        self.llm_adapter = OpenAILLMExtractor()
        # Instanciation de l'adaptateur Registre Entreprises SIRENE
        self.registry_adapter = SireneRegistryAPI()
        # Instanciation du repository SQLite sur disque
        self.db_adapter = SQLiteReceiptRepository()

        # Récupération du plafond repas depuis l'environnement
        max_meal = Decimal(os.getenv("MAX_MEAL_EXPENSE_EUR", "45.00"))

        # Compilation du graphe d'audit LangGraph
        self.audit_graph = build_audit_graph(
            ocr_engine=self.ocr_adapter,
            llm_extractor=self.llm_adapter,
            registry_service=self.registry_adapter,
            repository=self.db_adapter,
            max_meal_expense=max_meal,
        )

    # Méthode asynchrone pour envoyer un message texte à un utilisateur
    async def send_message(
        self,
        client: httpx.AsyncClient,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> None:
        # Préparation de l'URL d'envoi de message
        url = f"{self.api_url}/sendMessage"
        # Préparation des paramètres de la requête
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        # Envoi de la requête POST vers Telegram
        await client.post(url, json=payload)

    # Méthode asynchrone pour télécharger une photo envoyée sur Telegram
    async def download_photo(
        self, client: httpx.AsyncClient, file_id: str
    ) -> bytes:
        # Appel à getFile pour obtenir le chemin du fichier sur les serveurs Telegram
        get_file_url = f"{self.api_url}/getFile"
        # Envoi de la demande d'information de fichier
        response = await client.get(get_file_url, params={"file_id": file_id})
        # Décodage de la réponse JSON
        file_info = response.json()
        # Récupération du chemin relatif du fichier
        file_path = file_info["result"]["file_path"]
        # Construction de l'URL directe de téléchargement du binaire
        download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        # Téléchargement effectif du flux binaire de l'image
        img_response = await client.get(download_url)
        # Renvoi des octets de l'image
        return img_response.content

    # Méthode de formatage du rapport d'audit pour affichage sur smartphone
    def format_audit_message(self, decision: AuditDecision) -> str:
        # Cas 1 : Reçu validé sans réserve
        if decision.status == AuditStatus.APPROVED:
            # En-tête vert de succès
            header = "🟢 <b>REÇU CONFORME ET VALIDÉ</b>\n"
        # Cas 2 : Reçu nécessitant une vérification humaine
        elif decision.status == AuditStatus.FLAGGED_FOR_REVIEW:
            # En-tête orange d'avertissement
            header = "🟠 <b>REÇU EN ATTENTE DE VÉRIFICATION</b>\n"
        # Cas 3 : Reçu rejeté
        else:
            # En-tête rouge de rejet
            header = "🔴 <b>REÇU NON CONFORME / REJETÉ</b>\n"

        # Extraction des données financières
        data = decision.extracted_data
        # Si des données structurées ont pu être extraites
        if data:
            # Construction du bloc récapitulatif
            details = (
                f"\n🏢 <b>Commerçant :</b> {data.merchant.name}\n"
                f"📅 <b>Date :</b> {data.date}\n"
                f"💶 <b>Montant TTC :</b> {data.total_amount_ttc} {data.currency}\n"
                f"🏷️ <b>Catégorie :</b> {data.category.value}\n"
            )
            # Ajout de la validation légale SIRENE si présente
            if data.merchant.is_valid_in_registry is True:
                # Mention entreprise vérifiée
                details += "🏛️ <b>Registre SIRENE :</b> Entreprise active ✅\n"
            elif data.merchant.is_valid_in_registry is False:
                # Mention entreprise non reconnue
                details += "🏛️ <b>Registre SIRENE :</b> Non vérifié ou inactif ⚠️\n"
        else:
            # Détails indisponibles
            details = "\n<i>Données financières non extraites.</i>\n"

        # Ajout des motifs ou anomalies constatées
        reasons_text = ""
        # Vérification si des motifs existent
        if decision.reasons:
            # Concaténation des justifications
            reasons_text = "\n<b>Motifs :</b>\n" + "\n".join(
                f"• {r}" for r in decision.reasons
            )

        # Ajout du détail précis des anomalies (ex: erreur API)
        if decision.anomalies:
            # Concaténation des anomalies
            reasons_text += "\n\n<b>Détails techniques :</b>\n" + "\n".join(
                f"⚠️ [{a.rule_code}] {a.description}" for a in decision.anomalies
            )

        # Assemblage final du message
        return f"{header}{details}{reasons_text}\n\n🆔 <code>{decision.receipt_id}</code>"

    # Traitement individuel d'un message reçu
    async def process_update(
        self, client: httpx.AsyncClient, update: Dict[str, Any]
    ) -> None:
        # Récupération de l'objet message
        message = update.get("message")
        # Si aucun message n'est présent, ignorer
        if not message:
            # Sortie prématurée
            return

        # Récupération de l'identifiant de la conversation
        chat_id = message["chat"]["id"]
        # Récupération du texte si existant
        text = message.get("text", "")

        # Commande de démarrage /start
        if text.startswith("/start"):
            # Message de bienvenue et consignes d'utilisation
            welcome = (
                "👋 <b>Bienvenue sur ExpensyGuard !</b>\n\n"
                "📸 Envoyez-moi simplement la <b>photo de votre reçu ou ticket de caisse</b>.\n"
                "Je vais l'auditer automatiquement (OCR, vérification légale, règles de conformité)."
            )
            # Envoi du message d'accueil
            await self.send_message(client, chat_id, welcome)
            # Fin de traitement
            return

        # Vérification si le message contient une photo
        photos = message.get("photo")
        # Si aucune photo n'est présente
        if not photos:
            # Rappel à l'utilisateur
            await self.send_message(
                client,
                chat_id,
                "ℹ️ Veuillez m'envoyer une <b>photo claire</b> de votre ticket de caisse.",
            )
            # Fin de traitement
            return

        # Information à l'utilisateur que l'analyse est en cours
        await self.send_message(
            client,
            chat_id,
            "⏳ <i>Analyse et audit en cours (OCR + IA + Registre officiel)...</i>",
        )

        # Récupération de la photo avec la plus haute résolution (dernière de la liste)
        best_photo = photos[-1]
        # Identifiant du fichier Telegram
        file_id = best_photo["file_id"]

        # Bloc sécurisé d'exécution de l'audit
        try:
            # Téléchargement des octets de l'image
            image_bytes = await self.download_photo(client, file_id)
            # Création d'un identifiant unique de reçu
            receipt_id = f"tg_{uuid.uuid4().hex[:8]}"

            # Préparation de l'état initial pour LangGraph
            state = {
                "receipt_id": receipt_id,
                "image_bytes": image_bytes,
                "file_name": f"{receipt_id}.jpg",
                "anomalies": [],
            }

            # Affichage console pour suivi
            print(f"[INFO] Traitement du reçu {receipt_id}...")

            # Invocation asynchrone du pipeline d'audit
            result = await self.audit_graph.ainvoke(state)
            # Récupération de la décision produite
            decision = result.get("decision")

            # Si une décision a été émise
            if decision:
                # Formatage du texte de réponse
                reply_text = self.format_audit_message(decision)
            else:
                # Message d'erreur
                reply_text = "❌ <i>Échec du traitement du reçu.</i>"

            # Envoi du rapport final au smartphone de l'utilisateur
            await self.send_message(client, chat_id, reply_text)
            # Affichage console de confirmation
            print(f"[SUCCÈS] Reçu {receipt_id} audité : {decision.status.value if decision else 'ÉCHEC'}")

        # Capture des erreurs inattendues
        except Exception as err:
            # Journal d'erreur console
            print(f"[ERREUR] Échec de l'audit : {err}")
            # Notification d'erreur à l'utilisateur
            await self.send_message(
                client,
                chat_id,
                f"❌ <b>Erreur lors du traitement :</b>\n<code>{str(err)}</code>",
            )

    # Boucle principale d'écoute des messages (Long Polling)
    async def run_polling(self) -> None:
        # Message de démarrage dans la console
        print("[INFO] Bot Telegram ExpensyGuard démarré en écoute...")
        # Ouverture d'une session HTTP asynchrone
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Boucle infinie d'écoute
            while True:
                # Bloc de capture pour maintenir le bot actif en cas de coupure réseau
                try:
                    # Requête de récupération des nouveaux messages avec long polling (timeout 20s)
                    poll_url = f"{self.api_url}/getUpdates"
                    # Paramètres d'index et de délai d'attente
                    params = {"offset": self.offset, "timeout": 20}
                    # Appel GET bloquant vers Telegram
                    response = await client.get(poll_url, params=params)
                    # Décodage de la charge utile JSON
                    data = response.json()

                    # Parcours des messages reçus
                    for update in data.get("result", []):
                        # Mise à jour de l'offset pour acquitter le message
                        self.offset = update["update_id"] + 1
                        # Traitement asynchrone du message
                        await self.process_update(client, update)

                # Capture de l'interruption utilisateur (Ctrl+C)
                except asyncio.CancelledError:
                    # Message de clôture
                    print("\n[INFO] Arrêt du bot Telegram.")
                    # Sortie de boucle
                    break
                # Capture des erreurs réseau temporaires
                except Exception as loop_err:
                    # Affichage du journal d'erreur
                    print(f"[ATTENTION] Problème réseau Telegram: {loop_err}")
                    # Pause de 3 secondes avant reconnexion
                    await asyncio.sleep(3)


# Point d'entrée pour lancer le bot directement depuis le terminal
def main() -> None:
    # Chargement initial des variables d'environnement
    load_dotenv_custom()
    # Instanciation du bot
    bot = TelegramReceiptBot()
    # Exécution de la boucle asynchrone
    asyncio.run(bot.run_polling())


# Condition d'exécution de script direct
if __name__ == "__main__":
    # Lancement du bot
    main()
