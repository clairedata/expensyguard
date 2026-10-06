# ==============================================================================
# ADAPTATEUR BASE DE DONNÉES SQLITE (src/infrastructure/db_repository.py)
# Gestion de la persistance locale et détection d'empreinte unique SHA-256
# ==============================================================================

# Importation du module de gestion de contexte pour fermer proprement les connexions
from contextlib import contextmanager

# Importation du module standard de hachage cryptographique
import hashlib

# Importation du module JSON pour sérialiser les données d'audit
import json

# Importation du module standard de base de données SQLite
import sqlite3

# Importation du module de calcul financier Decimal
from decimal import Decimal

# Importation des types pour annoter le code
from typing import Generator, Optional

# Importation relative des modèles de domaine
from ..domain.models import (
    AuditDecision,
    DuplicateCheckResult,
    ReceiptExtraction,
)

# Importation relative du port de référentiel de reçus
from ..domain.ports import ReceiptRepositoryPort


# Implémentation du référentiel de stockage SQLite
class SQLiteReceiptRepository(ReceiptRepositoryPort):
    # Constructeur initialisant le chemin de la base et créant les tables
    def __init__(self, db_path: str = "expensyguard.db"):
        # Stockage du chemin de la base de données (fichier ou :memory:)
        self.db_path = db_path
        # Indicateur booléen vérifiant si la base est volatile en mémoire RAM
        self._is_memory = db_path == ":memory:"
        # Si la base est en mémoire, on maintient une connexion unique persistante
        if self._is_memory:
            # Création de la connexion unique persistante pour la RAM
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)
            # Permet d'accéder aux colonnes SQL par leurs noms
            self._persistent_conn.row_factory = sqlite3.Row
        else:
            # Pas de connexion persistante nécessaire pour les fichiers sur disque
            self._persistent_conn = None
        # Initialisation du schéma relationnel de la base
        self._init_db()

    # Gestionnaire de contexte sécurisé pour obtenir une connexion active
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        # Cas 1 : Base de données en mémoire RAM (tests unitaires / intégration)
        if self._is_memory:
            # Ouverture d'une transaction sécurisée sur la connexion persistante
            with self._persistent_conn:
                # Mise à disposition de la connexion
                yield self._persistent_conn
        # Cas 2 : Base de données enregistrée sur disque (production)
        else:
            # Ouverture d'une nouvelle connexion vers le fichier SQLite
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Activation du formatage des résultats en dictionnaires
            conn.row_factory = sqlite3.Row
            # Bloc de capture pour garantir la fermeture systématique
            try:
                # Ouverture de la transaction
                with conn:
                    # Mise à disposition de la connexion
                    yield conn
            # Fermeture obligatoire de la connexion disque en sortie de bloc
            finally:
                # Fermeture du descripteur de fichier
                conn.close()

    # Méthode interne d'initialisation des tables de la base de données
    def _init_db(self) -> None:
        # Récupération de la connexion via le gestionnaire de contexte
        with self._get_connection() as conn:
            # Création de la table des reçus stockant l'empreinte unique
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT UNIQUE NOT NULL,
                    merchant_name TEXT NOT NULL,
                    receipt_date TEXT NOT NULL,
                    total_amount_ttc TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    extracted_json TEXT,
                    audit_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Création d'un index sur l'empreinte pour accélérer les recherches de doublons
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_receipts_fingerprint 
                ON receipts(fingerprint)
                """
            )

    # Calcul de l'empreinte unique SHA-256 standardisée
    def compute_fingerprint(self, merchant_name: str, date_str: str, amount: Decimal) -> str:
        # Nettoyage et mise en minuscules du nom du commerçant
        normalized_merchant = merchant_name.strip().lower()
        # Nettoyage de la chaîne de date
        normalized_date = date_str.strip()
        # Formatage strict du montant à 2 décimales pour éviter toute divergence
        normalized_amount = f"{amount:.2f}"
        # Concaténation des trois valeurs séparées par un caractère pipe
        raw_signature = f"{normalized_merchant}|{normalized_date}|{normalized_amount}"
        # Calcul du condensat SHA-256 en hexadécimal
        return hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()

    # Détection de doublon en base à partir de l'empreinte
    def check_duplicate(self, fingerprint: str) -> DuplicateCheckResult:
        # Connexion à la base de données
        with self._get_connection() as conn:
            # Préparation et exécution de la requête de recherche d'empreinte
            cursor = conn.execute(
                "SELECT id FROM receipts WHERE fingerprint = ?",
                (fingerprint,),
            )
            # Récupération de la première ligne correspondante
            row = cursor.fetchone()
            # Si un enregistrement est trouvé, il s'agit d'un doublon avéré
            if row:
                # Renvoi d'un résultat positif avec l'ID du reçu original
                return DuplicateCheckResult(
                    is_duplicate=True,
                    fingerprint=fingerprint,
                    existing_receipt_id=row["id"],
                )
            # Aucun reçu identique n'a été trouvé
            return DuplicateCheckResult(
                is_duplicate=False,
                fingerprint=fingerprint,
                existing_receipt_id=None,
            )

    # Sauvegarde des résultats complets d'un audit de reçu
    def save_audit(
        self,
        receipt_id: str,
        fingerprint: str,
        extraction: Optional[ReceiptExtraction],
        decision: AuditDecision,
    ) -> None:
        # Sérialisation des données extraites en JSON
        extracted_json = extraction.model_dump_json() if extraction else None
        # Sérialisation de la décision finale d'audit en JSON
        audit_json = decision.model_dump_json()
        # Extraction du nom du commerçant ou valeur par défaut
        merchant_name = extraction.merchant.name if extraction else "INCONNU"
        # Extraction de la date ou valeur par défaut
        receipt_date = extraction.date if extraction else "1970-01-01"
        # Extraction du montant TTC ou valeur par défaut
        total_amount_ttc = str(extraction.total_amount_ttc) if extraction else "0.00"

        # Connexion à la base pour insérer l'enregistrement
        with self._get_connection() as conn:
            # Insertion avec gestion de conflit (remplacement si ré-audit forcé)
            conn.execute(
                """
                INSERT OR REPLACE INTO receipts (
                    id, fingerprint, merchant_name, receipt_date, 
                    total_amount_ttc, status, confidence_score, 
                    extracted_json, audit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    fingerprint,
                    merchant_name,
                    receipt_date,
                    total_amount_ttc,
                    decision.status.value,
                    decision.confidence_score,
                    extracted_json,
                    audit_json,
                ),
            )
