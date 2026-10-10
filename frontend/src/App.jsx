// ==============================================================================
// APPLICATION REACT PRINCIPALE (frontend/src/App.jsx)
// Dashboard interactif avec navigation par onglets dédiés et liaison API
// ==============================================================================

// Importation de React et des hooks d'état et d'effets
import React, { useState, useEffect } from 'react';

// Importation des icônes professionnelles depuis lucide-react
import {
  ShieldCheck,
  UploadCloud,
  Search,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  TrendingUp,
  DollarSign,
  Building2,
  Calendar,
  ChevronRight,
  X,
  LayoutDashboard,
  Sparkles,
  ArrowRight,
  Receipt
} from 'lucide-react';

// URL de base de l'API (utilise le proxy Vite configuré vers http://127.0.0.1:8000)
const API_BASE_URL = '';

// Composant racine de l'application
export default function App() {
  // Onglet actif : 'DASHBOARD' ou 'AUDIT'
  const [activeTab, setActiveTab] = useState('DASHBOARD');

  // Liste des reçus récupérés depuis l'API
  const [receipts, setReceipts] = useState([]);

  // Métriques consolidées pour les cartes KPI
  const [stats, setStats] = useState({
    total_receipts: 0,
    total_spent_eur: 0,
    approved_count: 0,
    review_count: 0,
    rejected_count: 0,
    compliance_rate: 100,
  });

  // État de chargement réseau
  const [loading, setLoading] = useState(false);

  // Filtre de statut actif pour le tableau
  const [filterStatus, setFilterStatus] = useState('ALL');

  // Chaîne de recherche pour filtrer commerçants et montants
  const [searchTerm, setSearchTerm] = useState('');

  // Reçu sélectionné pour affichage dans la modale d'inspection
  const [selectedReceipt, setSelectedReceipt] = useState(null);

  // Fichier sélectionné dans l'onglet d'audit
  const [auditFile, setAuditFile] = useState(null);

  // URL de prévisualisation locale de l'image
  const [previewUrl, setPreviewUrl] = useState(null);

  // État de progression de l'audit en cours
  const [isAuditing, setIsAuditing] = useState(false);

  // Résultat direct du dernier audit réalisé
  const [latestAuditResult, setLatestAuditResult] = useState(null);

  // Message d'erreur éventuel lors de l'audit
  const [auditError, setAuditError] = useState(null);

  // Fonction asynchrone de récupération des données depuis FastAPI
  const fetchData = async () => {
    // Activation de l'indicateur de chargement
    setLoading(true);

    try {
      // 1. Récupération des statistiques consolidées
      console.log(`[Frontend] Envoi de la requête vers : ${API_BASE_URL}/api/v1/stats`);
      const statsRes = await fetch(`${API_BASE_URL}/api/v1/stats`);
      console.log(`[Frontend] Statut HTTP stats :`, statsRes.status);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        console.log("[Frontend] Données stats reçues avec succès :", statsData);
        setStats(statsData);
      } else {
        console.warn("[Frontend] Échec de la réponse stats :", statsRes.status);
      }

      // 2. Récupération de la liste historique des reçus
      console.log(`[Frontend] Envoi de la requête vers : ${API_BASE_URL}/api/v1/receipts`);
      const receiptsRes = await fetch(`${API_BASE_URL}/api/v1/receipts`);
      console.log(`[Frontend] Statut HTTP receipts :`, receiptsRes.status);
      if (receiptsRes.ok) {
        const receiptsData = await receiptsRes.json();
        console.log("[Frontend] Liste des reçus reçue :", receiptsData);
        setReceipts(receiptsData);
      } else {
        console.warn("[Frontend] Échec de la réponse receipts :", receiptsRes.status);
      }
    } catch (err) {
      // Journalisation explicite si le serveur est éteint
      console.error("[Frontend] Erreur réseau (le serveur FastAPI est-il bien allumé sur le port 8000 ?) :", err);
    } finally {
      // Désactivation de l'indicateur de chargement
      setLoading(false);
    }
  };

  // Chargement automatique des données au montage du composant
  useEffect(() => {
    fetchData();
  }, []);

  // Gestionnaire de sélection de fichier dans l'onglet d'audit dédié
  const handleFileSelect = (event) => {
    // Récupération du fichier choisi
    const file = event.target.files?.[0];
    if (file) {
      // Stockage de l'objet fichier
      setAuditFile(file);
      // Réinitialisation des erreurs et résultats précédents
      setAuditError(null);
      setLatestAuditResult(null);
      // Création d'une URL de prévisualisation dans le DOM
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  // Gestionnaire d'exécution de l'audit complet via l'API
  const handleRunAudit = async () => {
    // Vérification de la présence d'un fichier
    if (!auditFile) return;

    // Préparation des données binaires multipart/form-data
    const formData = new FormData();
    formData.append('file', auditFile);

    // Démarrage de l'état d'audit
    setIsAuditing(true);
    setAuditError(null);

    try {
      // Appel POST vers la route d'audit de FastAPI
      const response = await fetch(`${API_BASE_URL}/api/v1/audit`, {
        method: 'POST',
        body: formData,
      });

      // Si le backend renvoie un statut 200 OK
      if (response.ok) {
        // Extraction de la décision d'audit retournée
        const resultData = await response.json();
        // Enregistrement dans l'état local pour affichage
        setLatestAuditResult(resultData);
        // Actualisation automatique de la liste globale et des KPI
        await fetchData();
      } else {
        // Lecture du message d'erreur retourné par l'API
        const errData = await response.json().catch(() => ({ detail: "Erreur serveur" }));
        setAuditError(errData.detail || "Échec du traitement du reçu.");
      }
    } catch (err) {
      // Capture d'erreur réseau
      console.error("Erreur d'audit:", err);
      setAuditError("Impossible de joindre le serveur d'audit FastAPI (vérifiez qu'il tourne sur le port 8000).");
    } finally {
      // Arrêt du loader d'audit
      setIsAuditing(false);
    }
  };

  // Gestionnaire de mise à jour manuelle du statut d'un reçu (Approve / Reject)
  const handleUpdateStatus = async (receiptId, newStatus) => {
    try {
      // Requête PATCH vers l'API
      const res = await fetch(`${API_BASE_URL}/api/v1/receipts/${receiptId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, note: "Décision manuelle du gestionnaire" }),
      });

      if (res.ok) {
        // Fermeture de la modale d'inspection
        setSelectedReceipt(null);
        // Rechargement des données fraîches
        await fetchData();
      }
    } catch (err) {
      console.error("Erreur de mise à jour du statut:", err);
    }
  };

  // Filtrage combiné des reçus (statut + barre de recherche)
  const filteredReceipts = receipts.filter((item) => {
    // Vérification du filtre par onglet
    const matchesStatus = filterStatus === 'ALL' || item.status === filterStatus;
    // Vérification de la correspondance textuelle
    const matchesSearch =
      (item.merchant_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.total_amount_ttc || '').includes(searchTerm);
    return matchesStatus && matchesSearch;
  });

  // Rendu visuel d'un badge de statut formaté
  const renderStatusPill = (status) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="status-pill status-approved">
            <CheckCircle2 size={12} /> Validé
          </span>
        );
      case 'FLAGGED_FOR_REVIEW':
        return (
          <span className="status-pill status-review">
            <AlertTriangle size={12} /> À Vérifier
          </span>
        );
      case 'REJECTED':
      default:
        return (
          <span className="status-pill status-rejected">
            <XCircle size={12} /> Rejeté
          </span>
        );
    }
  };

  return (
    <div className="app-container">
      {/* 1. En-tête principal et navigation par onglets */}
      <header className="app-header">
        <div className="brand-title">
          <ShieldCheck size={28} color="#2563eb" />
          <span>ExpensyGuard</span>
          <span className="brand-badge">Audit Automatisé</span>
        </div>

        {/* Barre de navigation entre Tableau de bord et Audit dédié */}
        <nav className="main-nav">
          <button
            className={`nav-btn ${activeTab === 'DASHBOARD' ? 'active' : ''}`}
            onClick={() => setActiveTab('DASHBOARD')}
          >
            <LayoutDashboard size={16} />
            Tableau de Bord & KPIs
          </button>
          <button
            className={`nav-btn ${activeTab === 'AUDIT' ? 'active' : ''}`}
            onClick={() => setActiveTab('AUDIT')}
          >
            <UploadCloud size={16} />
            Auditer un Reçu
          </button>
        </nav>

        {/* Bouton d'actualisation manuelle */}
        <button className="btn btn-outline" onClick={fetchData} title="Rafraîchir les données">
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Actualiser
        </button>
      </header>

      {/* ========================================================================= */}
      {/* VUE 1 : TABLEAU DE BORD (KPIS & HISTORIQUE DES REÇUS)                    */}
      {/* ========================================================================= */}
      {activeTab === 'DASHBOARD' && (
        <div>
          {/* Grille des 4 indicateurs KPI */}
          <section className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-header">
                <span>Total Dépenses</span>
                <DollarSign size={18} color="#2563eb" />
              </div>
              <div className="kpi-value">{(stats.total_spent_eur ?? 0).toFixed(2)} €</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span>Taux de Conformité</span>
                <TrendingUp size={18} color="#059669" />
              </div>
              <div className="kpi-value">{stats.compliance_rate ?? 100}%</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span>Reçus Validés</span>
                <CheckCircle2 size={18} color="#059669" />
              </div>
              <div className="kpi-value">{stats.approved_count ?? 0}</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span>À Réviser</span>
                <AlertTriangle size={18} color="#d97706" />
              </div>
              <div className="kpi-value" style={{ color: (stats.review_count ?? 0) > 0 ? '#d97706' : 'inherit' }}>
                {stats.review_count ?? 0}
              </div>
            </div>
          </section>

          {/* Barre de contrôles et filtres */}
          <div className="controls-bar">
            <div className="search-box">
              <Search size={16} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Rechercher par commerçant ou ID..."
                className="search-input"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <div className="filter-tabs">
              {['ALL', 'APPROVED', 'FLAGGED_FOR_REVIEW', 'REJECTED'].map((st) => (
                <button
                  key={st}
                  className={`filter-tab ${filterStatus === st ? 'active' : ''}`}
                  onClick={() => setFilterStatus(st)}
                >
                  {st === 'ALL' ? 'Tous' : st === 'APPROVED' ? 'Validés' : st === 'FLAGGED_FOR_REVIEW' ? 'À Réviser' : 'Rejetés'}
                </button>
              ))}
            </div>
          </div>

          {/* Tableau des reçus */}
          <div className="table-card">
            <table className="receipts-table">
              <thead>
                <tr>
                  <th>ID Reçu</th>
                  <th>Commerçant</th>
                  <th>Date</th>
                  <th>Montant TTC</th>
                  <th>Statut</th>
                  <th>Score IA</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredReceipts.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      Aucun reçu enregistré pour le moment dans la base.
                    </td>
                  </tr>
                ) : (
                  filteredReceipts.map((receipt) => (
                    <tr key={receipt.id} onClick={() => setSelectedReceipt(receipt)}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '0.8125rem' }}>
                        {receipt.id}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        {receipt.merchant_name || "Commerçant Inconnu"}
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>
                        {receipt.receipt_date || "-"}
                      </td>
                      <td style={{ fontWeight: 700 }}>
                        {receipt.total_amount_ttc || "0.00"} €
                      </td>
                      <td>
                        {renderStatusPill(receipt.status)}
                      </td>
                      <td>
                        <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                          {((receipt.confidence_score ?? 0) * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td style={{ textAlign: 'right', color: 'var(--text-muted)' }}>
                        <ChevronRight size={16} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VUE 2 : ESPACE DÉDIÉ D'AUDIT D'UNE NOUVELLE IMAGE                        */}
      {/* ========================================================================= */}
      {activeTab === 'AUDIT' && (
        <div className="audit-container">
          {/* Colonne gauche : Téléversement et Prévisualisation */}
          <div className="audit-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <UploadCloud size={20} color="#2563eb" />
              Importer une Photo de Reçu
            </h3>

            {/* Zone de drop */}
            <div
              className="upload-dropzone"
              onClick={() => document.getElementById('receipt-file-input').click()}
            >
              <input
                id="receipt-file-input"
                type="file"
                accept="image/*,application/pdf"
                style={{ display: 'none' }}
                onChange={handleFileSelect}
              />
              <Receipt size={40} color="#2563eb" style={{ margin: '0 auto 0.75rem auto' }} />
              <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                {auditFile ? auditFile.name : "Cliquez ou glissez une image ici"}
              </p>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                Formats acceptés : PNG, JPG, JPEG, PDF
              </p>
            </div>

            {/* Prévisualisation de l'image sélectionnée */}
            {previewUrl && (
              <div className="preview-box">
                <img src={previewUrl} alt="Aperçu du ticket" className="preview-image" />
              </div>
            )}

            {/* Bouton de déclenchement de l'audit */}
            <div style={{ marginTop: '1.25rem' }}>
              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
                onClick={handleRunAudit}
                disabled={!auditFile || isAuditing}
              >
                {isAuditing ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Audit LangGraph en cours (OCR + IA + Règles)...
                  </>
                ) : (
                  <>
                    <Sparkles size={18} />
                    Lancer l'Audit Automatique
                  </>
                )}
              </button>
            </div>

            {/* Message d'erreur éventuel */}
            {auditError && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', color: '#dc2626', fontSize: '0.8125rem' }}>
                <AlertTriangle size={16} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} />
                {auditError}
              </div>
            )}
          </div>

          {/* Colonne droite : Résultat direct de l'audit */}
          <div className="audit-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldCheck size={20} color="#059669" />
              Résultat d'Audit en Temps Réel
            </h3>

            {!latestAuditResult && !isAuditing && (
              <div style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--text-muted)' }}>
                <FileText size={48} style={{ margin: '0 auto 1rem auto', opacity: 0.4 }} />
                <p>Sélectionnez une image à gauche et cliquez sur <b>Lancer l'Audit</b> pour voir les extractions et vérifications.</p>
              </div>
            )}

            {isAuditing && (
              <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                <RefreshCw size={36} className="animate-spin" color="#2563eb" style={{ margin: '0 auto 1rem auto' }} />
                <h4 style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Analyse multi-agents en cours</h4>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  1. Détection de texte OCR $\rightarrow$ 2. Extraction structurée IA $\rightarrow$ 3. Registre SIRENE $\rightarrow$ 4. Règles fiscales
                </p>
              </div>
            )}

            {latestAuditResult && !isAuditing && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* Statut et ID */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      ID: {latestAuditResult.receipt_id}
                    </span>
                    <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.15rem' }}>
                      {latestAuditResult.extracted_data?.merchant?.name || "Commerçant Non Détecté"}
                    </h4>
                  </div>
                  <div>
                    {renderStatusPill(latestAuditResult.status)}
                  </div>
                </div>

                {/* Données clés extraites */}
                <div className="detail-row">
                  <span className="detail-label">Date :</span>
                  <span className="detail-value">{latestAuditResult.extracted_data?.date || "-"}</span>
                </div>

                <div className="detail-row">
                  <span className="detail-label">Montant Total TTC :</span>
                  <span className="detail-value" style={{ color: '#2563eb', fontSize: '1.1rem' }}>
                    {latestAuditResult.extracted_data?.total_amount_ttc || "0.00"} {latestAuditResult.extracted_data?.currency || "EUR"}
                  </span>
                </div>

                <div className="detail-row">
                  <span className="detail-label">Catégorie :</span>
                  <span className="detail-value">{latestAuditResult.extracted_data?.category || "AUTRE"}</span>
                </div>

                <div className="detail-row">
                  <span className="detail-label">Score de Confiance :</span>
                  <span className="detail-value">{((latestAuditResult.confidence_score ?? 0) * 100).toFixed(0)}%</span>
                </div>

                {/* Motifs et justifications */}
                {latestAuditResult.reasons && latestAuditResult.reasons.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: '0.5rem 0 0.25rem 0' }}>Motifs :</h4>
                    <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {latestAuditResult.reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Bouton pour basculer vers le tableau complet */}
                <button
                  className="btn btn-outline"
                  style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                  onClick={() => setActiveTab('DASHBOARD')}
                >
                  Voir dans le Tableau de Bord
                  <ArrowRight size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALE DE RÉVISION DÉTAILLÉE D'UN REÇU                                  */}
      {/* ========================================================================= */}
      {selectedReceipt && (
        <div className="modal-backdrop" onClick={() => setSelectedReceipt(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Fiche d'Audit du Reçu</h2>
                <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  ID #{selectedReceipt.id}
                </span>
              </div>
              <button className="btn btn-outline" onClick={() => setSelectedReceipt(null)} style={{ padding: '0.25rem 0.5rem' }}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="detail-row">
                <span className="detail-label">Commerçant émetteur</span>
                <span className="detail-value">{selectedReceipt.merchant_name || "Inconnu"}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Date de transaction</span>
                <span className="detail-value">{selectedReceipt.receipt_date || "-"}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Montant Total TTC</span>
                <span className="detail-value" style={{ fontSize: '1.1rem', color: '#2563eb' }}>
                  {selectedReceipt.total_amount_ttc || "0.00"} €
                </span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Statut d'audit</span>
                <span>{renderStatusPill(selectedReceipt.status)}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Empreinte SHA-256</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {selectedReceipt.fingerprint ? `${selectedReceipt.fingerprint.substring(0, 16)}...` : "-"}
                </span>
              </div>

              {/* Articles extraits si disponibles */}
              {selectedReceipt.extracted?.items && selectedReceipt.extracted.items.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: '0.75rem 0 0.5rem 0' }}>Articles Détectés :</h4>
                  <div className="items-list">
                    {selectedReceipt.extracted.items.map((it, idx) => (
                      <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
                        <span>{it.quantity}x {it.label}</span>
                        <span style={{ fontWeight: 600 }}>{it.total_price} €</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Motifs d'audit */}
              {selectedReceipt.audit?.reasons && selectedReceipt.audit.reasons.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: '0.75rem 0 0.25rem 0' }}>Motifs d'Audit :</h4>
                  <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {selectedReceipt.audit.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Actions de validation/rejet */}
            <div className="actions-footer">
              <button
                className="btn btn-danger"
                onClick={() => handleUpdateStatus(selectedReceipt.id, 'REJECTED')}
              >
                Rejeter
              </button>
              <button
                className="btn btn-success"
                onClick={() => handleUpdateStatus(selectedReceipt.id, 'APPROVED')}
              >
                Valider Définitivement
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
