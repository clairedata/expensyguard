# ==============================================================================
# NŒUDS ATOMIQUES DU GRAPHE LANGGRAPH (src/application/nodes.py)
# Chaque fonction représente une étape isolée et testable du pipeline d'audit
# ==============================================================================

# Importation du module de calcul décimal
from decimal import Decimal

# Importation des types pour annoter les fonctions du graphe
from typing import Any, Dict

# Importation relative des modèles métiers et statuts
from ..domain.models import (
    Anomaly,
    AuditDecision,
    AuditStatus,
    DuplicateCheckResult,
    ExpenseCategory,
    ReceiptExtraction,
)

# Importation relative des ports du domaine
from ..domain.ports import (
    LLMExtractorPort,
    OCREnginePort,
    ReceiptRepositoryPort,
    RegistryServicePort,
)

# Importation relative du schéma d'état de l'application
from .state import AuditFlowState


# Nœud 1 : Exécution de l'OCR sur l'image binaire
def ocr_node(state: AuditFlowState, ocr_engine: OCREnginePort) -> Dict[str, Any]:
    # Récupération des octets de l'image depuis l'état
    image_bytes = state.get("image_bytes", b"")
    # Initialisation de la liste des anomalies à partir de l'état existant
    anomalies = list(state.get("anomalies", []))

    # Vérification si l'image est absente ou vide
    if not image_bytes:
        # Enregistrement d'une anomalie critique de fichier manquant
        anomalies.append(
            Anomaly(
                rule_code="ERR_EMPTY_FILE",
                severity="CRITICAL",
                description="Le fichier d'image fourni est vide ou corrompu.",
            )
        )
        # Renvoi de l'état mis à jour avec erreur
        return {
            "ocr_raw_text": "",
            "anomalies": anomalies,
            "error_message": "Fichier image manquant",
        }

    # Bloc d'exécution sécurisé pour l'OCR
    try:
        # Appel de l'adaptateur OCR pour extraire le texte
        raw_text = ocr_engine.extract_text(image_bytes)
        # Vérification si aucun texte n'a été détecté par l'OCR
        if not raw_text:
            # Ajout d'une anomalie signalant une image illisible
            anomalies.append(
                Anomaly(
                    rule_code="WARN_UNREADABLE_IMAGE",
                    severity="WARNING",
                    description="Aucun texte n'a pu être extrait par l'OCR.",
                )
            )
        # Renvoi du texte extrait et de la liste d'anomalies
        return {"ocr_raw_text": raw_text, "anomalies": anomalies}
    # Capture des erreurs inattendues lors de l'OCR
    except Exception as exc:
        # Ajout d'une anomalie en cas de plantage du moteur OCR
        anomalies.append(
            Anomaly(
                rule_code="ERR_OCR_FAILURE",
                severity="CRITICAL",
                description=f"Erreur durant l'étape OCR : {str(exc)}",
            )
        )
        # Renvoi de l'état d'échec
        return {
            "ocr_raw_text": "",
            "anomalies": anomalies,
            "error_message": f"Échec OCR: {str(exc)}",
        }


# Nœud 2 : Extraction structurée des données via le LLM
def llm_extraction_node(
    state: AuditFlowState,
    llm_extractor: LLMExtractorPort,
) -> Dict[str, Any]:
    # Récupération du texte OCR brut
    raw_text = state.get("ocr_raw_text", "")
    # Récupération des anomalies accumulées
    anomalies = list(state.get("anomalies", []))

    # Si le texte OCR est vide, impossible de procéder à l'extraction LLM
    if not raw_text.strip():
        # Ajout d'une anomalie explicite
        anomalies.append(
            Anomaly(
                rule_code="ERR_NO_OCR_TEXT",
                severity="CRITICAL",
                description="Impossible d'exécuter l'extraction LLM sans texte OCR.",
            )
        )
        # Renvoi immédiat
        return {"extracted_data": None, "anomalies": anomalies}

    # Bloc sécurisé pour l'appel au modèle d'intelligence artificielle
    try:
        # Exécution de l'extraction structurée par le modèle
        extraction = llm_extractor.extract_receipt(raw_text)
        # Renvoi des données typées extraites
        return {"extracted_data": extraction, "anomalies": anomalies}
    # Capture des erreurs de validation ou d'API LLM
    except Exception as exc:
        # Ajout de l'anomalie correspondante
        anomalies.append(
            Anomaly(
                rule_code="ERR_LLM_PARSING",
                severity="CRITICAL",
                description=f"Erreur d'extraction par le LLM : {str(exc)}",
            )
        )
        # Renvoi d'un résultat d'extraction vide
        return {
            "extracted_data": None,
            "anomalies": anomalies,
            "error_message": f"Échec LLM: {str(exc)}",
        }


# Nœud 3 : Vérification légale du commerçant auprès du registre officiel (SIRENE)
async def registry_validation_node(
    state: AuditFlowState,
    registry_service: RegistryServicePort,
) -> Dict[str, Any]:
    # Récupération des données extraites du reçu
    extracted = state.get("extracted_data")
    # Récupération de la liste des anomalies
    anomalies = list(state.get("anomalies", []))

    # Si aucune donnée n'a été extraite, ignorer la validation
    if not extracted:
        # Poursuite du flux sans modification
        return {"registry_verification": None, "anomalies": anomalies}

    # Priorité à la recherche par SIREN/SIRET si disponible, sinon par nom
    search_term = extracted.merchant.siren_or_siret or extracted.merchant.name
    # Appel asynchrone du service SIRENE
    verification_result = await registry_service.verify_merchant(search_term)

    # Analyse du résultat retourné par le registre
    if not verification_result.get("is_found", False):
        # Ajout d'une anomalie : commerçant non trouvé dans les bases officielles
        anomalies.append(
            Anomaly(
                rule_code="WARN_MERCHANT_NOT_FOUND",
                severity="WARNING",
                description=f"Le commerçant '{search_term}' n'a pas été identifié dans le registre officiel des entreprises.",
            )
        )
        # Mise à jour du flag de validation sur l'entité commerçant
        extracted.merchant.is_valid_in_registry = False
    # Si l'entreprise est fermée ou radiée
    elif not verification_result.get("is_active", True):
        # Ajout d'une anomalie critique : entreprise inactive
        anomalies.append(
            Anomaly(
                rule_code="ERR_MERCHANT_INACTIVE",
                severity="CRITICAL",
                description="L'entreprise est enregistrée comme inactive ou radiée auprès du registre officiel.",
            )
        )
        # Marquer comme invalide
        extracted.merchant.is_valid_in_registry = False
    # L'entreprise existe légalement et est en activité
    else:
        # Marquer le commerçant comme officiellement validé
        extracted.merchant.is_valid_in_registry = True

    # Renvoi du résultat de vérification légale
    return {
        "registry_verification": verification_result,
        "extracted_data": extracted,
        "anomalies": anomalies,
    }


# Nœud 4 : Détection d'empreinte unique et blocage des doublons
def duplicate_detection_node(
    state: AuditFlowState,
    repo: ReceiptRepositoryPort,
) -> Dict[str, Any]:
    # Récupération des données extraites
    extracted = state.get("extracted_data")
    # Récupération des anomalies
    anomalies = list(state.get("anomalies", []))

    # Si aucune donnée n'a été extraite, calcul d'empreinte impossible
    if not extracted:
        # Renvoi sans résultat de doublon
        return {"duplicate_check": None, "anomalies": anomalies}

    # Calcul de l'empreinte cryptographique SHA-256 standardisée
    fingerprint = repo.compute_fingerprint(
        merchant_name=extracted.merchant.name,
        date_str=extracted.date,
        amount=extracted.total_amount_ttc,
    )

    # Interrogation du référentiel pour vérifier l'existence de cette empreinte
    dup_result = repo.check_duplicate(fingerprint)

    # Si l'empreinte existe déjà en base de données
    if dup_result.is_duplicate:
        # Ajout d'une anomalie critique de doublon
        anomalies.append(
            Anomaly(
                rule_code="ERR_DUPLICATE_RECEIPT",
                severity="CRITICAL",
                description=f"Ce reçu est un doublon exact du reçu ID #{dup_result.existing_receipt_id}.",
            )
        )

    # Renvoi du résultat de vérification de doublon
    return {"duplicate_check": dup_result, "anomalies": anomalies}


# Nœud 5 : Application des règles métier et arbitrage de la décision finale
def business_rules_and_decision_node(
    state: AuditFlowState,
    repo: ReceiptRepositoryPort,
    max_meal_expense: Decimal = Decimal("45.00"),
) -> Dict[str, Any]:
    # Récupération de l'identifiant du reçu ou génération par défaut
    receipt_id = state.get("receipt_id", "rec_default")
    # Récupération des données extraites
    extracted = state.get("extracted_data")
    # Récupération de la vérification de doublon
    dup_check = state.get("duplicate_check")
    # Récupération de la liste consolidée des anomalies
    anomalies = list(state.get("anomalies", []))
    # Initialisation de la liste des justifications
    reasons = []

    # Cas 1 : Absence totale de données extraites (échec amont)
    if not extracted:
        # Construction d'une décision de rejet
        decision = AuditDecision(
            receipt_id=receipt_id,
            status=AuditStatus.REJECTED,
            reasons=["Impossible d'extraire les données financières du document fourni."],
            anomalies=anomalies,
            confidence_score=0.0,
            extracted_data=None,
        )
        # Renvoi de la décision
        return {"decision": decision}

    # Cas 2 : Reçu identifié comme doublon
    if dup_check and dup_check.is_duplicate:
        # Motif explicite de rejet pour doublon
        reasons.append(f"Doublon détecté avec le reçu #{dup_check.existing_receipt_id}")
        # Construction de la décision de rejet
        decision = AuditDecision(
            receipt_id=receipt_id,
            status=AuditStatus.REJECTED,
            reasons=reasons,
            anomalies=anomalies,
            confidence_score=0.98,
            extracted_data=extracted,
        )
        # Renvoi de la décision sans écraser le doublon existant
        return {"decision": decision}

    # Application de la règle métier : Plafond des frais de repas
    if extracted.category == ExpenseCategory.MEAL and extracted.total_amount_ttc > max_meal_expense:
        # Ajout d'une anomalie d'avertissement de dépassement de plafond
        anomalies.append(
            Anomaly(
                rule_code="WARN_MEAL_CAP_EXCEEDED",
                severity="WARNING",
                description=f"Le montant du repas ({extracted.total_amount_ttc} €) dépasse le plafond autorisé de {max_meal_expense} €.",
            )
        )
        # Ajout d'une justification explicative
        reasons.append(f"Dépassement du plafond repas ({extracted.total_amount_ttc} € > {max_meal_expense} €)")

    # Vérification de la cohérence mathématique des montants
    if extracted.items:
        # Calcul de la somme des lignes d'articles
        sum_items = sum(item.total_price for item in extracted.items)
        # Tolérance de divergence d'arrondi de 0.05 €
        if abs(sum_items - extracted.total_amount_ttc) > Decimal("0.05"):
            # Signalement d'une anomalie d'incohérence arithmétique
            anomalies.append(
                Anomaly(
                    rule_code="WARN_ITEM_TOTAL_MISMATCH",
                    severity="WARNING",
                    description=f"La somme des articles ({sum_items} €) ne correspond pas au total TTC ({extracted.total_amount_ttc} €).",
                )
            )
            # Ajout d'un motif
            reasons.append("Incohérence entre la somme des articles et le total TTC")

    # Calcul du statut final en fonction des anomalies rencontrées
    has_critical = any(a.severity == "CRITICAL" for a in anomalies)
    # Vérification de la présence d'avertissements nécessitant revue
    has_warning = any(a.severity == "WARNING" for a in anomalies)

    # Si une anomalie critique est présente, rejet
    if has_critical:
        # Statut REJECTED
        final_status = AuditStatus.REJECTED
        # Score de confiance réduit
        confidence = 0.4
    # Si un avertissement est présent, revue manuelle requise
    elif has_warning:
        # Statut FLAGGED_FOR_REVIEW
        final_status = AuditStatus.FLAGGED_FOR_REVIEW
        # Score de confiance modéré
        confidence = 0.8
    # Aucune anomalie détectée : validation sans réserve
    else:
        # Statut APPROVED
        final_status = AuditStatus.APPROVED
        # Confirmation dans les motifs
        reasons.append("Reçu entièrement conforme aux règles de conformité et de gestion.")
        # Score de confiance maximal
        confidence = 0.99

    # Instanciation de la décision finale
    decision = AuditDecision(
        receipt_id=receipt_id,
        status=final_status,
        reasons=reasons,
        anomalies=anomalies,
        confidence_score=confidence,
        extracted_data=extracted,
    )

    # Récupération de l'empreinte pour enregistrement
    fingerprint = dup_check.fingerprint if dup_check else repo.compute_fingerprint(
        extracted.merchant.name, extracted.date, extracted.total_amount_ttc
    )

    # Sauvegarde de la décision d'audit dans la base de données
    repo.save_audit(
        receipt_id=receipt_id,
        fingerprint=fingerprint,
        extraction=extracted,
        decision=decision,
    )

    # Renvoi de l'état finalisé avec la décision
    return {"decision": decision}
