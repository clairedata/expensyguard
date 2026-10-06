# ==============================================================================
# INTERFACE EN LIGNE DE COMMANDE (src/interfaces/cli.py)
# Permet d'auditer un reçu depuis un terminal en appelant le graphe LangGraph
# ==============================================================================

# Importation du module d'analyse des arguments de ligne de commande
import argparse

# Importation du module asyncio pour exécuter le graphe asynchrone
import asyncio

# Importation du module JSON pour afficher un rapport formaté
import json

# Importation du module de gestion de chemins de fichiers
import os

# Importation du module UUID pour générer un ID de reçu unique
import uuid

# Importation du module de conversion décimale
from decimal import Decimal

# Importation relative du constructeur de graphe
from ..application.graph import build_audit_graph

# Importation relative des adaptateurs d'infrastructure réels
from ..infrastructure.db_repository import SQLiteReceiptRepository
from ..infrastructure.llm_adapter import OpenAILLMExtractor
from ..infrastructure.ocr_adapter import EasyOCREngine
from ..infrastructure.registry_api import SireneRegistryAPI


# Fonction principale asynchrone du CLI
async def main_async(image_path: str, max_meal_expense: str) -> None:
    # Vérification de l'existence du fichier d'image passé en argument
    if not os.path.exists(image_path):
        # Affichage d'un message d'erreur si le fichier est introuvable
        print(f"[ERREUR] Le fichier spécifié est introuvable : {image_path}")
        # Fin d'exécution
        return

    # Lecture des octets binaires de l'image
    with open(image_path, "rb") as file_handle:
        # Stockage du contenu binaire
        image_bytes = file_handle.read()

    # Affichage du message de lancement
    print(f"[INFO] Lancement de l'audit pour le fichier : {image_path}")

    # Instanciation de l'adaptateur OCR
    ocr_adapter = EasyOCREngine()
    # Instanciation de l'adaptateur LLM
    llm_adapter = OpenAILLMExtractor()
    # Instanciation de l'adaptateur Registre Entreprises
    registry_adapter = SireneRegistryAPI()
    # Instanciation du référentiel de base de données SQLite
    db_adapter = SQLiteReceiptRepository()

    # Construction du graphe d'audit compilé
    app_graph = build_audit_graph(
        ocr_engine=ocr_adapter,
        llm_extractor=llm_adapter,
        registry_service=registry_adapter,
        repository=db_adapter,
        max_meal_expense=Decimal(max_meal_expense),
    )

    # Préparation de l'état initial pour l'exécution
    initial_state = {
        "receipt_id": f"cli_{uuid.uuid4().hex[:8]}",
        "image_bytes": image_bytes,
        "file_name": os.path.basename(image_path),
        "anomalies": [],
    }

    # Invocation asynchrone du graphe LangGraph
    final_output = await app_graph.ainvoke(initial_state)

    # Récupération de la décision finale
    decision = final_output.get("decision")

    # Affichage des résultats
    print("\n" + "=" * 50)
    print("           RAPPORT D'AUDIT EXPENSYGUARD           ")
    print("=" * 50)
    # Affichage formaté JSON de la décision
    if decision:
        # Sérialisation avec indentation
        print(json.dumps(decision.model_dump(), indent=2, ensure_ascii=False))
    else:
        # Message d'erreur
        print("[ERREUR] Aucune décision n'a pu être produite.")
    print("=" * 50 + "\n")


# Point d'entrée standard du script CLI
def main() -> None:
    # Création du parseur d'arguments CLI
    parser = argparse.ArgumentParser(
        description="ExpensyGuard CLI - Audit automatique de reçu et note de frais."
    )
    # Argument obligatoire : chemin de l'image
    parser.add_argument(
        "--image",
        "-i",
        required=True,
        help="Chemin vers le fichier image du reçu à analyser (JPEG, PNG).",
    )
    # Argument optionnel : seuil repas
    parser.add_argument(
        "--max-meal",
        default=os.getenv("MAX_MEAL_EXPENSE_EUR", "45.00"),
        help="Plafond de dépense autorisé pour les repas en euros (défaut: 45.00).",
    )
    # Analyse des arguments de la ligne de commande
    args = parser.parse_args()
    # Exécution de la boucle asynchrone
    asyncio.run(main_async(args.image, args.max_meal))


# Condition d'exécution directe
if __name__ == "__main__":
    # Appel de la fonction principale
    main()
