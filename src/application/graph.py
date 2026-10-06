# ==============================================================================
# ASSEMBLAGE DU GRAPHE LANGGRAPH (src/application/graph.py)
# Orchestration agentique sous forme de machine à états déterministe et asynchrone
# ==============================================================================

# Importation du module de calcul décimal
from decimal import Decimal

# Importation des types pour annoter les signatures de fonctions
from typing import Any, Dict

# Importation des constantes de contrôle et de la classe StateGraph de LangGraph
from langgraph.graph import END, START, StateGraph

# Importation relative des ports d'infrastructure définis dans le domaine
from ..domain.ports import (
    LLMExtractorPort,
    OCREnginePort,
    ReceiptRepositoryPort,
    RegistryServicePort,
)

# Importation relative des fonctions de nœuds atomiques de traitement
from .nodes import (
    business_rules_and_decision_node,
    duplicate_detection_node,
    llm_extraction_node,
    ocr_node,
    registry_validation_node,
)

# Importation relative du schéma d'état partagé du flux d'audit
from .state import AuditFlowState


# Fonction de fabrique pour construire et compiler le graphe d'audit
def build_audit_graph(
    ocr_engine: OCREnginePort,
    llm_extractor: LLMExtractorPort,
    registry_service: RegistryServicePort,
    repository: ReceiptRepositoryPort,
    max_meal_expense: Decimal = Decimal("45.00"),
) -> Any:
    # Instanciation du graphe d'état typé avec le schéma AuditFlowState
    workflow = StateGraph(AuditFlowState)

    # Nœud 1 : Enveloppe asynchrone pour l'exécution du prétraitement et de l'OCR
    async def _run_ocr(state: AuditFlowState) -> Dict[str, Any]:
        # Appel synchrone de la fonction ocr_node encapsulé dans une coroutine
        return ocr_node(state, ocr_engine)

    # Nœud 2 : Enveloppe asynchrone pour l'extraction structurée LLM
    async def _run_llm(state: AuditFlowState) -> Dict[str, Any]:
        # Appel de l'extracteur LLM avec les modèles Pydantic
        return llm_extraction_node(state, llm_extractor)

    # Nœud 3 : Enveloppe asynchrone pour l'interrogation du registre officiel SIRENE
    async def _run_registry(state: AuditFlowState) -> Dict[str, Any]:
        # Appel asynchrone du service SIRENE avec attente await
        return await registry_validation_node(state, registry_service)

    # Nœud 4 : Enveloppe asynchrone pour le calcul d'empreinte et détection de doublons
    async def _run_duplicate_check(state: AuditFlowState) -> Dict[str, Any]:
        # Appel du vérificateur d'empreinte SHA-256 en base SQLite
        return duplicate_detection_node(state, repository)

    # Nœud 5 : Enveloppe asynchrone pour l'arbitrage des règles métier et statut final
    async def _run_business_rules(state: AuditFlowState) -> Dict[str, Any]:
        # Évaluation des règles métier (plafond repas, arithmétique, cohérence globale)
        return business_rules_and_decision_node(
            state, repository, max_meal_expense=max_meal_expense
        )

    # Ajout du nœud OCR au graphe
    workflow.add_node("ocr", _run_ocr)
    # Ajout du nœud d'extraction LLM au graphe
    workflow.add_node("llm_extraction", _run_llm)
    # Ajout du nœud de vérification du registre légal au graphe
    workflow.add_node("registry_validation", _run_registry)
    # Ajout du nœud de détection des doublons au graphe
    workflow.add_node("duplicate_check", _run_duplicate_check)
    # Ajout du nœud de décision et d'application des règles métier au graphe
    workflow.add_node("business_rules", _run_business_rules)

    # Définition de l'arête reliant le point de départ START au nœud OCR
    workflow.add_edge(START, "ocr")
    # Définition de l'arête reliant le nœud OCR au nœud d'extraction LLM
    workflow.add_edge("ocr", "llm_extraction")
    # Définition de l'arête reliant le nœud LLM à la vérification SIRENE
    workflow.add_edge("llm_extraction", "registry_validation")
    # Définition de l'arête reliant la vérification SIRENE à la détection de doublon
    workflow.add_edge("registry_validation", "duplicate_check")
    # Définition de l'arête reliant la détection de doublon aux règles métier
    workflow.add_edge("duplicate_check", "business_rules")
    # Définition de l'arête reliant les règles métier au point final END
    workflow.add_edge("business_rules", END)

    # Compilation finale du graphe d'états
    return workflow.compile()
