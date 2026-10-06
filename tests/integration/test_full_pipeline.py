# ==============================================================================
# TESTS D'INTÉGRATION DU PIPELINE COMPLET (tests/integration/test_full_pipeline.py)
# Valide l'exécution de la machine d'états LangGraph avec des mocks de ports
# ==============================================================================

# Importation du module de calcul décimal
from decimal import Decimal

# Importation des types
from typing import Any, Dict

# Importation du module pytest pour les tests asynchrones
import pytest

# Importation du générateur de graphe
from src.application.graph import build_audit_graph

# Importation des modèles de domaine
from src.domain.models import (
    AuditStatus,
    ExpenseCategory,
    MerchantInfo,
    ReceiptExtraction,
    ReceiptItem,
)

# Importation des ports
from src.domain.ports import (
    LLMExtractorPort,
    OCREnginePort,
    ReceiptRepositoryPort,
    RegistryServicePort,
)

# Importation du repository réel en mémoire
from src.infrastructure.db_repository import SQLiteReceiptRepository


# Mock simulant l'adaptateur OCR
class MockOCREngine(OCREnginePort):
    # Implémentation simulant le retour de texte
    def extract_text(self, image_bytes: bytes) -> str:
        # Retour d'un texte factice de ticket de caisse
        return "RESTAURANT LE GOURMET\nDATE: 2026-10-04\nTOTAL TTC: 30.00 EUR"


# Mock simulant l'adaptateur LLM
class MockLLMExtractor(LLMExtractorPort):
    # Constructeur permettant d'injecter une extraction personnalisée
    def __init__(self, extraction: ReceiptExtraction):
        # Stockage de l'extraction voulue
        self.extraction = extraction

    # Renvoi systématique de l'extraction simulée
    def extract_receipt(self, ocr_text: str) -> ReceiptExtraction:
        # Renvoi de l'objet
        return self.extraction


# Mock simulant l'API SIRENE
class MockRegistryService(RegistryServicePort):
    # Implémentation renvoyant un commerçant actif
    async def verify_merchant(self, query: str) -> Dict[str, Any]:
        # Retour simulé d'entreprise valide
        return {
            "is_found": True,
            "siren": "987654321",
            "nom_complet": "LE GOURMET SARL",
            "is_active": True,
        }


# Test d'intégration asynchrone du workflow complet
@pytest.mark.asyncio
async def test_full_pipeline_approved():
    # Création d'une extraction conforme
    sample_extraction = ReceiptExtraction(
        merchant=MerchantInfo(name="Le Gourmet", siren_or_siret="987654321"),
        date="2026-10-04",
        total_amount_ttc=Decimal("30.00"),
        currency="EUR",
        category=ExpenseCategory.MEAL,
        items=[
            ReceiptItem(label="Menu du jour", total_price=Decimal("30.00")),
        ],
    )

    # Instanciation des faux adaptateurs
    ocr = MockOCREngine()
    llm = MockLLMExtractor(sample_extraction)
    registry = MockRegistryService()
    repo = SQLiteReceiptRepository(db_path=":memory:")

    # Construction du graphe avec plafond repas à 45.00 EUR
    graph = build_audit_graph(
        ocr_engine=ocr,
        llm_extractor=llm,
        registry_service=registry,
        repository=repo,
        max_meal_expense=Decimal("45.00"),
    )

    # Préparation de l'état initial
    initial_state = {
        "receipt_id": "test_001",
        "image_bytes": b"fake_image_bytes",
        "file_name": "ticket.png",
        "anomalies": [],
    }

    # Exécution du graphe
    result = await graph.ainvoke(initial_state)

    # Récupération de la décision finale
    decision = result.get("decision")

    # Assertions sur le résultat
    assert decision is not None
    # Vérification que le reçu est validé (APPROVED)
    assert decision.status == AuditStatus.APPROVED
    # Vérification du score de confiance
    assert decision.confidence_score > 0.90


# Test d'intégration pour le rejet des doublons
@pytest.mark.asyncio
async def test_duplicate_rejection():
    # Extraction type
    sample_extraction = ReceiptExtraction(
        merchant=MerchantInfo(name="Le Gourmet", siren_or_siret="987654321"),
        date="2026-10-04",
        total_amount_ttc=Decimal("30.00"),
        currency="EUR",
        category=ExpenseCategory.MEAL,
        items=[
            ReceiptItem(label="Menu", total_price=Decimal("30.00")),
        ],
    )

    # Adaptateurs
    ocr = MockOCREngine()
    llm = MockLLMExtractor(sample_extraction)
    registry = MockRegistryService()
    repo = SQLiteReceiptRepository(db_path=":memory:")

    # Graphe
    graph = build_audit_graph(
        ocr_engine=ocr,
        llm_extractor=llm,
        registry_service=registry,
        repository=repo,
        max_meal_expense=Decimal("45.00"),
    )

    # Premier passage pour enregistrer le reçu en base
    await graph.ainvoke({
        "receipt_id": "receipt_original",
        "image_bytes": b"fake_bytes",
        "file_name": "receipt1.png",
        "anomalies": [],
    })

    # Deuxième passage avec un autre ID mais données identiques (doublon)
    second_result = await graph.ainvoke({
        "receipt_id": "receipt_duplicate",
        "image_bytes": b"fake_bytes",
        "file_name": "receipt2.png",
        "anomalies": [],
    })

    # Récupération de la décision du doublon
    duplicate_decision = second_result.get("decision")

    # Vérification que le doublon a été REJETÉ
    assert duplicate_decision is not None
    assert duplicate_decision.status == AuditStatus.REJECTED
    assert any("Doublon" in r for r in duplicate_decision.reasons)
