# ==============================================================================
# ÉTAT DE LA MACHINE D'ÉTATS LANGGRAPH (src/application/state.py)
# Définition du schéma de données transitant entre les nœuds du pipeline
# ==============================================================================

# Importation des types génériques et TypedDict pour la gestion d'état LangGraph
from typing import Any, Dict, List, Optional, TypedDict

# Importation relative des modèles de domaine
from ..domain.models import (
    Anomaly,
    AuditDecision,
    DuplicateCheckResult,
    ReceiptExtraction,
)


# Structure de données représentant l'état complet du flux d'audit d'un reçu
class AuditFlowState(TypedDict, total=False):
    # Identifiant unique de la transaction ou de l'audit
    receipt_id: str

    # Données brutes binaires du fichier image ou PDF reçu
    image_bytes: bytes

    # Nom d'origine du fichier transmis
    file_name: str

    # Texte brut extrait par le moteur OCR
    ocr_raw_text: str

    # Données structurées extraites par le modèle LLM
    extracted_data: Optional[ReceiptExtraction]

    # Résultat de la validation auprès de l'API légale SIRENE
    registry_verification: Optional[Dict[str, Any]]

    # Résultat de la vérification de doublon en base SQL
    duplicate_check: Optional[DuplicateCheckResult]

    # Liste cumulée des anomalies détectées tout au long du graphe
    anomalies: List[Anomaly]

    # Décision finale consolidée issue de l'audit
    decision: Optional[AuditDecision]

    # Message d'erreur éventuel en cas d'interruption du graphe
    error_message: Optional[str]
