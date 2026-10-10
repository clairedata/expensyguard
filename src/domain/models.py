# ==============================================================================
# MODÈLES DE DONNÉES DU DOMAINE MÉTIER (src/domain/models.py)
# Architecture Hexagonale : Entités pures et immuables, sans dépendance externe
# ==============================================================================

# Importation du module de calcul décimal pour éviter les erreurs d'arrondi financier
from decimal import Decimal

# Importation du module d'énumération standard pour typer les statuts
from enum import Enum

# Importation des types optionnels et listes pour les annotations de type
from typing import Any, Dict, List, Optional

# Importation des briques de base de validation Pydantic V2
from pydantic import BaseModel, Field, field_validator, model_validator


# Définition de l'énumération représentant les statuts finaux d'audit
class AuditStatus(str, Enum):
    # Statut indiquant que le reçu est conforme et validé
    APPROVED = "APPROVED"
    # Statut indiquant qu'une anomalie nécessite une vérification humaine
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"
    # Statut indiquant un refus catégorique (ex: faux commerçant, doublon avéré)
    REJECTED = "REJECTED"


# Définition des catégories de dépenses professionnelles
class ExpenseCategory(str, Enum):
    # Dépense liée à la restauration ou aux repas d'affaires
    MEAL = "MEAL"
    # Dépense liée au transport (train, avion, taxi, carburant)
    TRANSPORT = "TRANSPORT"
    # Dépense liée à l'hébergement (hôtel, logement temporaire)
    HOTEL = "HOTEL"
    # Dépense liée aux fournitures de bureau et petits équipements
    SUPPLIES = "SUPPLIES"
    # Autre catégorie de dépense non répertoriée
    OTHER = "OTHER"


# Modèle représentant les informations légales et administratives du commerçant
class MerchantInfo(BaseModel):
    # Nom commercial ou raison sociale de l'établissement
    name: str = Field(description="Nom ou enseigne du commerçant")
    # Numéro SIREN (9 chiffres) ou SIRET (14 chiffres) identifiant l'entreprise en France
    siren_or_siret: Optional[str] = Field(default=None, description="Identifiant SIREN ou SIRET si extrait")
    # Adresse physique du lieu de vente ou siège social
    address: Optional[str] = Field(default=None, description="Adresse mentionnée sur le ticket")
    # Indicateur confirmant la validité légale de l'entreprise après vérification du registre
    is_valid_in_registry: Optional[bool] = Field(default=None, description="Validé auprès de l'API SIRENE")


# Modèle détaillant la ventilation de la Taxe sur la Valeur Ajoutée (TVA)
class TaxDetail(BaseModel):
    # Taux de TVA appliqué en pourcentage (ex: 20.0, 10.0, 5.5, ou None si non précisé)
    rate: Optional[Decimal] = Field(default=None, description="Taux de TVA en pourcentage")
    # Montant net hors taxe sur lequel s'applique ce taux
    net_amount: Optional[Decimal] = Field(default=None, description="Base hors taxe soumise à ce taux")
    # Montant calculé de la taxe
    tax_amount: Optional[Decimal] = Field(default=None, description="Montant de la TVA correspondante")

    # Validateur pré-traitement pour tolérer les alias comme 'amount' renvoyés par l'IA
    @model_validator(mode="before")
    @classmethod
    def normalize_tax_fields(cls, data: Any) -> Any:
        # Si la donnée reçue est un dictionnaire
        if isinstance(data, dict):
            # Si le champ 'tax_amount' est absent mais 'amount' est présent
            if "tax_amount" not in data and "amount" in data:
                # Assigner 'amount' à 'tax_amount'
                data["tax_amount"] = data["amount"]
            # Si le champ 'rate' est manquant ou vide
            if "rate" not in data or data["rate"] is None:
                # On tolère None par défaut
                data["rate"] = None
        # Renvoi de la donnée normalisée
        return data


# Modèle représentant une ligne individuelle d'article sur le ticket de caisse
class ReceiptItem(BaseModel):
    # Libellé ou désignation de l'article acheté
    label: str = Field(default="Article", description="Désignation de l'article")
    # Quantité achetée (par défaut 1)
    quantity: Decimal = Field(default=Decimal("1.0"), description="Quantité d'articles achetés")
    # Prix unitaire de l'article
    unit_price: Optional[Decimal] = Field(default=None, description="Prix unitaire de l'article")
    # Prix total pour la ligne (quantité x prix unitaire)
    total_price: Optional[Decimal] = Field(default=None, description="Montant total de la ligne")

    # Validateur pré-traitement pour tolérer 'price' ou 'amount'
    @model_validator(mode="before")
    @classmethod
    def normalize_item_fields(cls, data: Any) -> Any:
        # Si la donnée reçue est un dictionnaire
        if isinstance(data, dict):
            # Si total_price est absent mais price est présent
            if "total_price" not in data and "price" in data:
                # Mapper price vers total_price
                data["total_price"] = data["price"]
        # Renvoi de la donnée normalisée
        return data


# Modèle représentant la structure complète des données extraites du reçu
class ReceiptExtraction(BaseModel):
    # Informations sur le commerçant émetteur
    merchant: MerchantInfo = Field(description="Commerçant émetteur du reçu")
    # Date d'émission de la facture au format ISO YYYY-MM-DD
    date: str = Field(description="Date de la transaction au format YYYY-MM-DD")
    # Heure de la transaction au format HH:MM si disponible
    time: Optional[str] = Field(default=None, description="Heure de la transaction")
    # Montant Total Toutes Taxes Comprises (TTC)
    total_amount_ttc: Decimal = Field(description="Montant total TTC payé")
    # Montant Total Hors Taxes (HT)
    total_amount_ht: Optional[Decimal] = Field(default=None, description="Montant total Hors Taxes")
    # Devise monétaire utilisée (par défaut l'Euro)
    currency: str = Field(default="EUR", description="Devise de la transaction (ex: EUR, USD)")
    # Catégorie de dépense détectée
    category: ExpenseCategory = Field(default=ExpenseCategory.OTHER, description="Catégorie de la dépense")
    # Liste détaillée des taxes appliquées
    taxes: List[TaxDetail] = Field(default_factory=list, description="Ventilation des taxes")
    # Liste détaillée des articles achetés
    items: List[ReceiptItem] = Field(default_factory=list, description="Articles figurant sur le reçu")

    # Validateur pour s'assurer que le total TTC est strictement positif
    @field_validator("total_amount_ttc")
    @classmethod
    def validate_positive_amount(cls, value: Decimal) -> Decimal:
        # Vérification si le montant est inférieur ou égal à zéro
        if value <= Decimal("0"):
            # Déclenchement d'une exception explicite en cas de montant invalide
            raise ValueError("Le montant total TTC doit être strictement supérieur à 0.")
        # Renvoi de la valeur validée
        return value


# Modèle représentant le résultat de la vérification des doublons
class DuplicateCheckResult(BaseModel):
    # Booléen indiquant si le reçu est un doublon détecté
    is_duplicate: bool = Field(description="Vrai si le reçu existe déjà dans la base")
    # Empreinte cryptographique unique calculée (hash)
    fingerprint: str = Field(description="Hash SHA256 identifiant le reçu de manière unique")
    # Identifiant du reçu déjà existant en cas de collision
    existing_receipt_id: Optional[str] = Field(default=None, description="ID du reçu existant si doublon")


# Modèle représentant une anomalie identifiée lors de l'audit
class Anomaly(BaseModel):
    # Code d'identification de la règle métier violée
    rule_code: str = Field(description="Code machine de l'anomalie détectée")
    # Niveau de gravité de l'anomalie (INFO, WARNING, CRITICAL)
    severity: str = Field(description="Gravité de l'anomalie")
    # Description compréhensible de l'anomalie
    description: str = Field(description="Explication textuelle de l'anomalie")


# Modèle représentant la décision finale de l'audit automatisé
class AuditDecision(BaseModel):
    # Identifiant unique de l'audit
    receipt_id: str = Field(description="Identifiant unique de la transaction ou du fichier")
    # Statut global attribué par le moteur de règles
    status: AuditStatus = Field(description="Statut final d'audit")
    # Liste des motifs ayant conduit à cette décision
    reasons: List[str] = Field(default_factory=list, description="Explications justificatives")
    # Liste des anomalies repérées lors des différentes étapes
    anomalies: List[Anomaly] = Field(default_factory=list, description="Liste des anomalies constatées")
    # Score de confiance global entre 0.0 et 1.0
    confidence_score: float = Field(default=1.0, description="Niveau de confiance global du résultat")
    # Données extraites associées au reçu si l'analyse a abouti
    extracted_data: Optional[ReceiptExtraction] = Field(default=None, description="Données structurées extraites")
