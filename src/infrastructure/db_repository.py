# ==============================================================================
# ADAPTATEUR BASE DE DONNÉES SQLITE (src/infrastructure/db_repository.py)
# Gestion de la persistance locale, détection d'empreinte SHA-256 et requêtes API
# ==============================================================================

# Importation du module de gestion de contexte pour fermer proprement les connexions
from contextlib import contextmanager

# Importation du module standard de hachage cryptographique
import hashlib

# Importation du module JSON pour sérialiser et désérialiser les données d'audit
import json

# Importation du module standard de base de données SQLite
import sqlite3

# Importation du module de calcul financier Decimal
from decimal import Decimal

# Importation du module pathlib pour les chemins absolus
from pathlib import Path

# Importation des types pour annoter le code
from typing import Any, Dict, Generator, List, Optional

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
    def __init__(self, db_path: Optional[str] = None):
        # Cas base de données volatile en mémoire RAM (utilisé uniquement en tests)
        if db_path == ":memory:":
            # Affectation du mot-clé :memory:
            self.db_path = ":memory:"
            # Indicateur de mémoire RAM
            self._is_memory = True
            # Connexion unique persistante pour la RAM
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)
            # Row factory pour accès par clé
            self._persistent_conn.row_factory = sqlite3.Row
        # Cas base de données persistante sur le disque dur (Production standard)
        else:
            # Calcul du chemin absolu basé sur la racine du projet
            project_root = Path(__file__).resolve().parent.parent.parent
            # Chemin absolu vers le fichier physique expensyguard.db
            self.db_path = db_path if db_path else str(project_root / "expensyguard.db")
            # Base physique sur disque
            self._is_memory = False
            # Pas de connexion persistante unique nécessaire
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
            # Création de la table des employés
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    department TEXT NOT NULL,
                    hire_date TEXT NOT NULL,
                    avatar_color TEXT DEFAULT '#2563eb',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

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
                    image_filename TEXT,
                    employee_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Migrations non destructives pour ajouter les colonnes si la base existait déjà
            try:
                conn.execute("ALTER TABLE receipts ADD COLUMN image_filename TEXT")
            except Exception:
                pass

            try:
                conn.execute("ALTER TABLE receipts ADD COLUMN employee_id TEXT")
            except Exception:
                pass

            # Création d'un index sur l'empreinte pour accélérer les recherches de doublons
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_receipts_fingerprint 
                ON receipts(fingerprint)
                """
            )

            # Création d'un index sur l'employé
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_receipts_employee 
                ON receipts(employee_id)
                """
            )

            # Insertion de données initiales d'employés si la table est vide
            cur = conn.execute("SELECT COUNT(*) as count FROM employees")
            if cur.fetchone()["count"] == 0:
                seed_employees = [
                    ("EMP001", "Alexandre Martin", "a.martin@entreprise.fr", "Commercial & Ventes", "2022-03-15", "#2563eb"),
                    ("EMP002", "Sophie Durand", "s.durand@entreprise.fr", "Marketing & Communication", "2023-06-01", "#7c3aed"),
                    ("EMP003", "Thomas Leroy", "t.leroy@entreprise.fr", "Ingénierie & Tech", "2021-11-10", "#059669"),
                    ("EMP004", "Élodie Petit", "e.petit@entreprise.fr", "Direction Générale", "2020-01-20", "#d97706"),
                ]
                conn.executemany(
                    "INSERT INTO employees (id, name, email, department, hire_date, avatar_color) VALUES (?, ?, ?, ?, ?, ?)",
                    seed_employees,
                )

            # Attribution d'un employé par défaut (EMP001) aux reçus existants sans employé
            conn.execute("UPDATE receipts SET employee_id = 'EMP001' WHERE employee_id IS NULL OR employee_id = ''")

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
        image_filename: Optional[str] = None,
        employee_id: Optional[str] = None,
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
            # Récupération d'éventuelles valeurs existantes si non fournies
            if image_filename is None or employee_id is None:
                try:
                    cur = conn.execute("SELECT image_filename, employee_id FROM receipts WHERE id = ?", (receipt_id,))
                    existing = cur.fetchone()
                    if existing:
                        if image_filename is None and existing["image_filename"]:
                            image_filename = existing["image_filename"]
                        if employee_id is None and existing["employee_id"]:
                            employee_id = existing["employee_id"]
                except Exception:
                    pass

            # Employé par défaut si toujours None
            if not employee_id:
                employee_id = "EMP001"

            # Insertion avec gestion de conflit (remplacement si ré-audit forcé)
            conn.execute(
                """
                INSERT OR REPLACE INTO receipts (
                    id, fingerprint, merchant_name, receipt_date, 
                    total_amount_ttc, status, confidence_score, 
                    extracted_json, audit_json, image_filename, employee_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    image_filename,
                    employee_id,
                ),
            )

    # Récupérer la liste complète des reçus enrichis avec les données employés
    def list_receipts(self, limit: int = 100) -> List[Dict[str, Any]]:
        # Connexion à la base de données
        with self._get_connection() as conn:
            # Sélection avec jointure optionnelle sur les employés
            cursor = conn.execute(
                """
                SELECT 
                    r.*,
                    e.name as employee_name,
                    e.department as employee_department,
                    e.avatar_color as employee_avatar_color
                FROM receipts r
                LEFT JOIN employees e ON r.employee_id = e.id
                ORDER BY r.created_at DESC 
                LIMIT ?
                """,
                (limit,),
            )
            # Récupération des lignes
            rows = cursor.fetchall()
            results = []
            for row in rows:
                audit_data = json.loads(row["audit_json"]) if row["audit_json"] else {}
                extracted_data = json.loads(row["extracted_json"]) if row["extracted_json"] else None
                img_file = row["image_filename"] if "image_filename" in row.keys() else None
                results.append({
                    "id": row["id"],
                    "fingerprint": row["fingerprint"],
                    "merchant_name": row["merchant_name"],
                    "receipt_date": row["receipt_date"],
                    "total_amount_ttc": row["total_amount_ttc"],
                    "status": row["status"],
                    "confidence_score": row["confidence_score"],
                    "created_at": row["created_at"],
                    "image_filename": img_file,
                    "image_url": f"/data_images/{img_file}" if img_file else None,
                    "employee_id": row["employee_id"] or "EMP001",
                    "employee_name": row["employee_name"] or "Employé",
                    "employee_department": row["employee_department"] or "Général",
                    "employee_avatar_color": row["employee_avatar_color"] or "#2563eb",
                    "audit": audit_data,
                    "extracted": extracted_data,
                })
            return results

    # Récupérer la liste de tous les employés
    def list_employees(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM employees ORDER BY name ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # Récupérer la fiche complète d'un employé avec statistiques filtrées dans le temps
    def get_employee_sheet(
        self,
        employee_id: str,
        period_type: str = "ALL",  # 'ALL', 'DAY', 'MONTH', 'YEAR'
        date_value: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            # Récupération de l'employé
            cur_emp = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
            emp = cur_emp.fetchone()
            if not emp:
                return None

            emp_dict = dict(emp)

            # Construction de la clause de filtrage temporel sur la date du reçu (ou date de création)
            query_conditions = ["employee_id = ?"]
            params: List[Any] = [employee_id]

            if period_type == "DAY" and date_value:
                query_conditions.append("(receipt_date = ? OR created_at LIKE ?)")
                params.extend([date_value, f"{date_value}%"])
            elif period_type == "MONTH" and date_value:
                query_conditions.append("(receipt_date LIKE ? OR created_at LIKE ?)")
                params.extend([f"{date_value}%", f"{date_value}%"])
            elif period_type == "YEAR" and date_value:
                query_conditions.append("(receipt_date LIKE ? OR created_at LIKE ?)")
                params.extend([f"{date_value}%", f"{date_value}%"])

            where_clause = " WHERE " + " AND ".join(query_conditions)

            # Calcul des métriques agrégées pour cette période
            stats_query = f"""
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(CASE WHEN status = 'APPROVED' THEN CAST(total_amount_ttc AS REAL) ELSE 0.0 END), 0.0) as total_sum,
                    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) as approved_count,
                    SUM(CASE WHEN status = 'FLAGGED_FOR_REVIEW' THEN 1 ELSE 0 END) as review_count,
                    SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count
                FROM receipts
                {where_clause}
            """
            cur_stats = conn.execute(stats_query, tuple(params))
            stats_row = cur_stats.fetchone()

            total_count = stats_row["total_count"] or 0
            total_sum = round(stats_row["total_sum"] or 0.0, 2)
            approved = stats_row["approved_count"] or 0
            review = stats_row["review_count"] or 0
            rejected = stats_row["rejected_count"] or 0

            # Récupération des reçus correspondants
            receipts_query = f"""
                SELECT * FROM receipts 
                {where_clause}
                ORDER BY receipt_date DESC, created_at DESC
            """
            cur_receipts = conn.execute(receipts_query, tuple(params))
            receipt_rows = cur_receipts.fetchall()

            receipts_list = []
            for r in receipt_rows:
                img_file = r["image_filename"] if "image_filename" in r.keys() else None
                receipts_list.append({
                    "id": r["id"],
                    "merchant_name": r["merchant_name"],
                    "receipt_date": r["receipt_date"],
                    "total_amount_ttc": r["total_amount_ttc"],
                    "status": r["status"],
                    "confidence_score": r["confidence_score"],
                    "created_at": r["created_at"],
                    "image_url": f"/data_images/{img_file}" if img_file else None,
                })

            return {
                "employee": emp_dict,
                "period": {
                    "type": period_type,
                    "date_value": date_value,
                },
                "stats": {
                    "total_receipts": total_count,
                    "total_spent_eur": total_sum,
                    "approved_count": approved,
                    "review_count": review,
                    "rejected_count": rejected,
                },
                "receipts": receipts_list,
            }

    # Suppression d'un reçu (Action réservée à l'administrateur)
    def delete_receipt(self, receipt_id: str) -> bool:
        with self._get_connection() as conn:
            # Récupération du nom de fichier image avant suppression
            cur = conn.execute("SELECT image_filename FROM receipts WHERE id = ?", (receipt_id,))
            row = cur.fetchone()
            if not row:
                return False

            img_file = row["image_filename"] if "image_filename" in row.keys() else None

            # Suppression de la ligne en base
            conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))

            # Suppression physique de l'image si elle existe sur disque
            if img_file:
                project_root = Path(__file__).resolve().parent.parent.parent
                img_path = project_root / "data_images" / img_file
                if img_path.exists():
                    try:
                        img_path.unlink()
                    except Exception:
                        pass

            return True

    # Récupérer les statistiques globales pour les cartes KPI du Frontend (ne compte que les reçus APPROVED)
    def get_statistics(self) -> Dict[str, Any]:
        # Connexion à la base
        with self._get_connection() as conn:
            # Requête d'agrégation globale - total_sum ne compte STRICTEMENT que les tickets 'APPROVED'
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(CASE WHEN status = 'APPROVED' THEN CAST(total_amount_ttc AS REAL) ELSE 0.0 END), 0.0) as total_sum,
                    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) as approved_count,
                    SUM(CASE WHEN status = 'FLAGGED_FOR_REVIEW' THEN 1 ELSE 0 END) as review_count,
                    SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count
                FROM receipts
                """
            )
            # Récupération de la ligne d'agrégation
            row = cursor.fetchone()
            # Construction des statistiques consolidées
            total_count = row["total_count"] or 0
            total_sum = round(row["total_sum"] or 0.0, 2)
            approved = row["approved_count"] or 0
            review = row["review_count"] or 0
            rejected = row["rejected_count"] or 0
            # Calcul du taux de conformité automatique en pourcentage
            compliance_rate = round((approved / total_count * 100), 1) if total_count > 0 else 100.0

            # Renvoi du dictionnaire de métriques pour le Dashboard
            return {
                "total_receipts": total_count,
                "total_spent_eur": total_sum,
                "approved_count": approved,
                "review_count": review,
                "rejected_count": rejected,
                "compliance_rate": compliance_rate,
            }

    # Mise à jour manuelle du statut d'un reçu par le comptable
    def update_receipt_status(self, receipt_id: str, new_status: str, note: Optional[str] = None) -> bool:
        # Connexion à la base
        with self._get_connection() as conn:
            # Récupération de l'audit existant
            cursor = conn.execute("SELECT audit_json FROM receipts WHERE id = ?", (receipt_id,))
            row = cursor.fetchone()
            # Si le reçu n'existe pas
            if not row:
                return False
            # Désérialisation de l'audit
            audit_dict = json.loads(row["audit_json"])
            # Mise à jour du statut
            audit_dict["status"] = new_status
            # Ajout de la note de révision si renseignée
            if note:
                audit_dict.setdefault("reasons", []).append(f"Validation manuelle : {note}")
            # Ré-enregistrement en base
            conn.execute(
                "UPDATE receipts SET status = ?, audit_json = ? WHERE id = ?",
                (new_status, json.dumps(audit_dict), receipt_id),
            )
            return True
