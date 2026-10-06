# ==============================================================================
# APPLICATION FASTAPI (src/interfaces/api/main.py)
# API REST exposant le service d'audit de reçus via upload de fichier
# ==============================================================================

# Importation du module standard de gestion des variables d'environnement
import os

# Importation de la génération d'identifiants uniques UUID
import uuid

# Importation du module de calcul décimal
from decimal import Decimal

# Importation des briques FastAPI
from fastapi import FastAPI, File, HTTPException, UploadFile, status

# Importation de la réponse JSON standardisée
from fastapi.responses import JSONResponse

# Importation relative du constructeur de graphe LangGraph
from ...application.graph import build_audit_graph

# Importation relative des modèles de domaine
from ...domain.models import AuditDecision

# Importation relative des adaptateurs d'infrastructure
from ...infrastructure.db_repository import SQLiteReceiptRepository
from ...infrastructure.llm_adapter import OpenAILLMExtractor
from ...infrastructure.ocr_adapter import EasyOCREngine
from ...infrastructure.registry_api import SireneRegistryAPI


# Initialisation de l'application FastAPI avec métadonnées professionnelles
app = FastAPI(
    title="ExpensyGuard API",
    description="Système d'audit automatisé de notes de frais et reçus en Clean Architecture",
    version="0.1.0",
)

# Instanciation globale des adaptateurs (Singletons pour injection)
ocr_adapter = EasyOCREngine()
llm_adapter = OpenAILLMExtractor()
registry_adapter = SireneRegistryAPI()
db_adapter = SQLiteReceiptRepository()

# Récupération du plafond repas depuis l'environnement
MAX_MEAL_EXPENSE = Decimal(os.getenv("MAX_MEAL_EXPENSE_EUR", "45.00"))

# Compilation du graphe d'audit global
audit_graph = build_audit_graph(
    ocr_engine=ocr_adapter,
    llm_extractor=llm_adapter,
    registry_service=registry_adapter,
    repository=db_adapter,
    max_meal_expense=MAX_MEAL_EXPENSE,
)


# Route de vérification de l'état de santé du service (Healthcheck)
@app.get("/health", tags=["Monitoring"], summary="Vérifier la disponibilité de l'API")
async def health_check() -> dict:
    # Renvoi d'un indicateur de statut opérationnel
    return {"status": "healthy", "service": "expensyguard"}


# Route principale d'upload et d'audit de reçu
@app.post(
    "/api/v1/audit",
    response_model=AuditDecision,
    status_code=status.HTTP_200_OK,
    tags=["Audit"],
    summary="Uploader et auditer un reçu fiscal ou ticket de caisse",
)
async def audit_receipt_endpoint(
    file: UploadFile = File(..., description="Image du reçu (PNG, JPEG, PDF)"),
) -> AuditDecision:
    # Vérification que le fichier a bien été transmis
    if not file.filename:
        # Levée d'une exception HTTP 400 en cas d'absence de fichier
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier valide n'a été fourni.",
        )

    # Bloc de traitement de la requête
    try:
        # Lecture asynchrone du flux binaire du fichier uploadé
        image_bytes = await file.read()
        # Génération d'un identifiant unique de transaction pour traçabilité
        receipt_id = f"api_{uuid.uuid4().hex[:10]}"

        # Préparation de l'état initial envoyé au graphe
        initial_state = {
            "receipt_id": receipt_id,
            "image_bytes": image_bytes,
            "file_name": file.filename,
            "anomalies": [],
        }

        # Exécution asynchrone du pipeline d'audit
        final_state = await audit_graph.ainvoke(initial_state)

        # Récupération de la décision générée
        decision = final_state.get("decision")

        # Vérification si une décision a bien été produite
        if not decision:
            # Levée d'une erreur interne si aucun résultat
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Le moteur d'audit n'a pas pu émettre de décision finale.",
            )

        # Renvoi de la décision validée
        return decision

    # Capture et renvoi structuré des erreurs
    except HTTPException:
        # Relance des exceptions HTTP standard
        raise
    except Exception as general_error:
        # Renvoi d'une erreur 500 explicative
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue lors de l'audit du reçu : {str(general_error)}",
        )
