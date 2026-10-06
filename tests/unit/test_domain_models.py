# ==============================================================================
# TESTS UNITAIRES DES MODÈLES DU DOMAINE (tests/unit/test_domain_models.py)
# Vérifie l'intégrité, la validation Pydantic et le calcul de précision décimale
# ==============================================================================

# Importation du module de calcul décimal
from decimal import Decimal

# Importation du framework de tests pytest
import pytest

# Importation des modèles à tester
from src.domain.models import (
    AuditDecision,
    AuditStatus,
    ExpenseCategory,
    MerchantInfo,
    ReceiptExtraction,
    ReceiptItem,
    TaxDetail,
)

# Importation de l'adaptateur de base de données pour tester le calcul d'empreinte
from src.infrastructure.db_repository import SQLiteReceiptRepository


# Test de création valide d'un modèle ReceiptExtraction
def test_valid_receipt_extraction():
    # Instanciation d'un commerçant
    merchant = MerchantInfo(
        name="Boulangerie Paul",
        siren_or_siret="123456789",
        address="10 Rue de la Paix, Paris",
    )
    # Instanciation d'une taxe
    tax = TaxDetail(
        rate=Decimal("10.0"),
        net_amount=Decimal("10.00"),
        tax_amount=Decimal("1.00"),
    )
    # Instanciation d'un article
    item = ReceiptItem(
        label="Sandwich Jambon",
        quantity=Decimal("1"),
        unit_price=Decimal("11.00"),
        total_price=Decimal("11.00"),
    )
    # Instanciation de l'extraction complète
    extraction = ReceiptExtraction(
        merchant=merchant,
        date="2026-10-04",
        total_amount_ttc=Decimal("11.00"),
        total_amount_ht=Decimal("10.00"),
        currency="EUR",
        category=ExpenseCategory.MEAL,
        taxes=[tax],
        items=[item],
    )
    # Vérification que le montant TTC est bien de 11.00
    assert extraction.total_amount_ttc == Decimal("11.00")
    # Vérification du nom du commerçant
    assert extraction.merchant.name == "Boulangerie Paul"
    # Vérification de la catégorie
    assert extraction.category == ExpenseCategory.MEAL


# Test de rejet lors d'un montant TTC négatif ou nul
def test_invalid_negative_amount():
    # Instanciation d'un commerçant
    merchant = MerchantInfo(name="Test Store")
    # Vérification qu'une exception ValueError est levée lors de la création avec montant <= 0
    with pytest.raises(ValueError):
        # Création avec montant total négatif
        ReceiptExtraction(
            merchant=merchant,
            date="2026-10-04",
            total_amount_ttc=Decimal("-5.00"),
        )


# Test de calcul d'empreinte cryptographique SHA-256
def test_fingerprint_generation():
    # Instanciation du repository en mémoire
    repo = SQLiteReceiptRepository(db_path=":memory:")
    # Calcul de l'empreinte pour un premier reçu
    fp1 = repo.compute_fingerprint("Bistro Parisien", "2026-10-04", Decimal("35.50"))
    # Calcul de l'empreinte avec casse différente et espaces (normalisation)
    fp2 = repo.compute_fingerprint("  bistro parisien  ", "2026-10-04", Decimal("35.50"))
    # Calcul avec montant différent
    fp3 = repo.compute_fingerprint("Bistro Parisien", "2026-10-04", Decimal("35.51"))

    # Vérification que les deux premières empreintes normalisées sont identiques
    assert fp1 == fp2
    # Vérification que l'empreinte avec montant différent diverge
    assert fp1 != fp3
