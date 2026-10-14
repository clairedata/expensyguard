# ==============================================================================
# APPLICATION FASTAPI (src/interfaces/api/main.py)
# API REST exposant le service d'audit et les données pour le Dashboard React
# ==============================================================================

# Importation du module standard de gestion des variables d'environnement
import os
from pathlib import Path

# Importation de la génération d'identifiants uniques UUID
import uuid

# Importation du module de calcul décimal
from decimal import Decimal

# Importation des types
from typing import Any, Dict, List, Optional

# Importation des briques FastAPI et du middleware CORS
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Importation relative du constructeur de graphe LangGraph
from ...application.graph import build_audit_graph

# Importation relative des modèles de domaine
from ...domain.models import AuditDecision

# Importation relative des adaptateurs d'infrastructure
from ...infrastructure.db_repository import SQLiteReceiptRepository
from ...infrastructure.llm_adapter import OpenAILLMExtractor
from ...infrastructure.ocr_adapter import EasyOCREngine
from ...infrastructure.registry_api import SireneRegistryAPI
from ...infrastructure.security import (
    LoginRequest,
    LoginResponse,
    UserPublic,
    authenticate_user,
    create_access_token,
    decode_access_token,
)


# Initialisation du dossier physique de stockage des images de reçus
DATA_IMAGES_DIR = Path(__file__).resolve().parent.parent.parent / "data_images"
DATA_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Initialisation de l'application FastAPI avec métadonnées professionnelles
app = FastAPI(
    title="ExpensyGuard API",
    description="API REST d'audit automatisé de reçus fiscaux, gestion des collaborateurs et contrôle d'accès JWT",
    version="0.2.0",
)

# Montage du répertoire d'images pour accès direct statique
app.mount("/data_images", StaticFiles(directory=str(DATA_IMAGES_DIR)), name="data_images")

# Configuration du middleware CORS pour autoriser le frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Modèle de requête pour la mise à jour de statut par le gestionnaire
class UpdateStatusRequest(BaseModel):
    status: str
    note: Optional[str] = None


# Dépendance de vérification du jeton JWT pour récupérer l'utilisateur connecté
async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[UserPublic]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").replace("bearer ", "").strip()
    payload = decode_access_token(token)
    if not payload or "username" not in payload:
        return None
    return UserPublic(
        username=payload["username"],
        name=payload.get("name", "Utilisateur"),
        email=payload.get("email", ""),
        role=payload.get("role", "user"),
    )


# Dépendance stricte exigeant les privilèges d'administrateur
async def require_admin(authorization: Optional[str] = Header(None)) -> UserPublic:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification JWT requise. Veuillez vous connecter.",
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action réservée aux administrateurs. Vos permissions sont insuffisantes pour supprimer un reçu.",
        )
    return user


# ==============================================================================
# ROUTES D'AUTHENTIFICATION (JWT)
# ==============================================================================

@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Auth"], summary="Connexion et obtention du JWT")
def login_endpoint(request: LoginRequest) -> LoginResponse:
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects. Veuillez vérifier votre nom d'utilisateur et mot de passe.",
        )
    token = create_access_token({
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    })
    return LoginResponse(access_token=token, token_type="bearer", user=user)


@app.get("/api/v1/auth/me", response_model=UserPublic, tags=["Auth"], summary="Profil de l'utilisateur connecté")
async def get_me_endpoint(user: Optional[UserPublic] = Depends(get_current_user)) -> UserPublic:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée.",
        )
    return user


# ==============================================================================
# ROUTES DES EMPLOYÉS & FICHES COLLABORATEURS
# ==============================================================================

@app.get("/api/v1/employees", tags=["Employees"], summary="Lister tous les collaborateurs")
def list_employees_endpoint() -> List[Dict[str, Any]]:
    return db_adapter.list_employees()


@app.get("/api/v1/employees/{employee_id}", tags=["Employees"], summary="Fiche détaillée d'un employé avec filtre temporel")
def get_employee_sheet_endpoint(
    employee_id: str,
    period_type: str = "ALL",  # ALL, DAY, MONTH, YEAR
    date_value: Optional[str] = None,
) -> Dict[str, Any]:
    sheet = db_adapter.get_employee_sheet(
        employee_id=employee_id,
        period_type=period_type.upper(),
        date_value=date_value,
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    return sheet


# ==============================================================================
# ROUTES DU DASHBOARD & HISTORIQUE DES REÇUS
# ==============================================================================

@app.get("/", tags=["Monitoring"], summary="Accueil de l'API")
def root_endpoint() -> dict:
    return {"message": "ExpensyGuard API en ligne", "docs": "/docs", "status": "healthy"}


@app.get("/health", tags=["Monitoring"], summary="Vérifier la disponibilité de l'API")
def health_check() -> dict:
    return {"status": "healthy", "service": "expensyguard"}


@app.get("/api/v1/stats", tags=["Dashboard"], summary="Obtenir les métriques globales")
def get_stats_endpoint() -> Dict[str, Any]:
    return db_adapter.get_statistics()


@app.get("/api/v1/receipts", tags=["Dashboard"], summary="Lister les reçus audités")
def list_receipts_endpoint(limit: int = 100) -> List[Dict[str, Any]]:
    return db_adapter.list_receipts(limit=limit)


@app.patch("/api/v1/receipts/{receipt_id}/status", tags=["Dashboard"], summary="Modifier le statut d'un reçu")
def update_status_endpoint(receipt_id: str, request: UpdateStatusRequest) -> dict:
    success = db_adapter.update_receipt_status(receipt_id, request.status, request.note)
    if not success:
        raise HTTPException(status_code=404, detail="Reçu introuvable.")
    return {"success": True, "receipt_id": receipt_id, "new_status": request.status}


# Route de suppression d'un reçu (Réservée exclusivement à l'Admin)
@app.delete(
    "/api/v1/receipts/{receipt_id}",
    tags=["Dashboard"],
    summary="Supprimer un reçu (Admin uniquement)",
)
async def delete_receipt_endpoint(
    receipt_id: str,
    admin_user: UserPublic = Depends(require_admin),
) -> dict:
    deleted = db_adapter.delete_receipt(receipt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reçu introuvable.")
    return {
        "success": True,
        "receipt_id": receipt_id,
        "deleted_by": admin_user.username,
        "message": f"Le reçu {receipt_id} a été définitivement supprimé par l'administrateur.",
    }


# ==============================================================================
# ROUTES D'AUDIT ET IMAGES
# ==============================================================================

@app.post(
    "/api/v1/audit",
    response_model=AuditDecision,
    status_code=status.HTTP_200_OK,
    tags=["Audit"],
    summary="Uploader et auditer un reçu fiscal ou ticket de caisse",
)
async def audit_receipt_endpoint(
    file: UploadFile = File(..., description="Image du reçu (PNG, JPEG, PDF)"),
    employee_id: Optional[str] = Form("EMP001", description="ID de l'employé soumettant le reçu"),
) -> AuditDecision:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier valide n'a été fourni.",
        )

    try:
        image_bytes = await file.read()
        receipt_id = f"api_{uuid.uuid4().hex[:10]}"

        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = ".png"
        image_filename = f"{receipt_id}{ext}"
        saved_image_path = DATA_IMAGES_DIR / image_filename

        with open(saved_image_path, "wb") as f_out:
            f_out.write(image_bytes)

        initial_state = {
            "receipt_id": receipt_id,
            "image_bytes": image_bytes,
            "file_name": image_filename,
            "employee_id": employee_id or "EMP001",
            "anomalies": [],
        }

        final_state = await audit_graph.ainvoke(initial_state)
        decision = final_state.get("decision")

        if not decision:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Le moteur d'audit n'a pas pu émettre de décision finale.",
            )

        return decision

    except HTTPException:
        raise
    except Exception as general_error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue lors de l'audit du reçu : {str(general_error)}",
        )


@app.get(
    "/api/v1/receipts/{receipt_id}/image",
    tags=["Dashboard"],
    summary="Récupérer l'image physique du reçu",
)
def get_receipt_image_endpoint(receipt_id: str):
    for ext in [".png", ".jpg", ".jpeg", ".pdf", ".webp"]:
        target_file = DATA_IMAGES_DIR / f"{receipt_id}{ext}"
        if target_file.exists():
            return FileResponse(target_file)

    matches = list(DATA_IMAGES_DIR.glob(f"*{receipt_id}*"))
    if matches and matches[0].is_file():
        return FileResponse(matches[0])

    raise HTTPException(status_code=404, detail="Image du reçu introuvable.")
