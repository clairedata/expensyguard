# ==============================================================================
# PORTS DU DOMAINE - INTERFACES ABSTRAITES (src/domain/ports.py)
# Architecture Hexagonale : Les contrats d'interface sans dépendance d'infrastructure
# ==============================================================================

# Importation du module ABC pour définir des classes de base abstraites
from abc import ABC, abstractmethod

# Importation du module Decimal pour manipuler des montants financiers précis
from decimal import Decimal

# Importation des types pour annoter les retours des fonctions
from typing import Any, Dict, Optional

# Importation relative des modèles de domaine nécessaires aux contrats d'interface
from .models import (
    AuditDecision,
    DuplicateCheckResult,
    ReceiptExtraction,
)


# Interface abstraite du moteur de reconnaissance optique de caractères (OCR)
class OCREnginePort(ABC):
    # Méthode abstraite pour extraire le texte brut à partir d'un flux binaire d'image
    @abstractmethod
    def extract_text(self, image_bytes: bytes) -> str:
        # Signature de la méthode d'extraction OCR
        pass


# Interface abstraite pour le moteur d'extraction structurée par modèle de langage (LLM)
class LLMExtractorPort(ABC):
    # Méthode abstraite pour transformer le texte brut OCR en objet structuré ReceiptExtraction
    @abstractmethod
    def extract_receipt(self, ocr_text: str) -> ReceiptExtraction:
        # Signature de la méthode d'extraction LLM
        pass


# Interface abstraite pour le service d'interrogation du registre public des entreprises
class RegistryServicePort(ABC):
    # Méthode abstraite asynchrone pour vérifier l'existence légale d'une entreprise
    @abstractmethod
    async def verify_merchant(self, query: str) -> Dict[str, Any]:
        # Signature de la méthode de vérification SIRENE
        pass


# Interface abstraite pour le référentiel de stockage et de détection des doublons
class ReceiptRepositoryPort(ABC):
    # Méthode abstraite pour calculer l'empreinte unique SHA256 d'un reçu
    @abstractmethod
    def compute_fingerprint(self, merchant_name: str, date_str: str, amount: Decimal) -> str:
        # Signature de calcul d'empreinte
        pass

    # Méthode abstraite pour vérifier si une empreinte existe déjà en base
    @abstractmethod
    def check_duplicate(self, fingerprint: str) -> DuplicateCheckResult:
        # Signature de vérification de doublon
        pass

    # Méthode abstraite pour enregistrer la décision et les données d'un reçu audité
    @abstractmethod
    def save_audit(
        self,
        receipt_id: str,
        fingerprint: str,
        extraction: Optional[ReceiptExtraction],
        decision: AuditDecision,
    ) -> None:
        # Signature de persistance de l'audit
        pass
