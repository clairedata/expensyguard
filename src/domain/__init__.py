# ==============================================================================
# FICHIER D'INITIALISATION DE LA COUCHE DOMAINE (src/domain/__init__.py)
# ==============================================================================

# Importation relative des modèles métiers et énumérations
from .models import (
    AuditDecision,
    AuditStatus,
    DuplicateCheckResult,
    ExpenseCategory,
    MerchantInfo,
    ReceiptExtraction,
    ReceiptItem,
    TaxDetail,
)

# Importation relative des interfaces abstraites (ports hexagonaux)
from .ports import (
    LLMExtractorPort,
    OCREnginePort,
    ReceiptRepositoryPort,
    RegistryServicePort,
)

# Exposition propre des symboles du domaine
__all__ = [
    "AuditDecision",
    "AuditStatus",
    "DuplicateCheckResult",
    "ExpenseCategory",
    "MerchantInfo",
    "ReceiptExtraction",
    "ReceiptItem",
    "TaxDetail",
    "LLMExtractorPort",
    "OCREnginePort",
    "ReceiptRepositoryPort",
    "RegistryServicePort",
]
