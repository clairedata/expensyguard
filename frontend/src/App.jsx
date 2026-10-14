// ==============================================================================
// APPLICATION REACT PRINCIPALE (frontend/src/App.jsx)
// Dashboard d'audit avec authentification JWT (Admin / User), gestion des employés
// et modale de fiche collaborateur avec filtres temporels (Jour / Mois / Année)
// ==============================================================================

import React, { useState, useEffect, useMemo } from 'react';

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
  Receipt,
  Eye,
  Image as ImageIcon,
  Trash2,
  User,
  Users,
  LogOut,
  LogIn,
  KeyRound,
  Filter,
  Clock,
  Briefcase,
  Mail,
  Crown,
  Shield,
  Lock
} from 'lucide-react';

const API_BASE_URL = '';

export default function App() {
  // Navigation active : 'DASHBOARD' ou 'AUDIT'
  const [activeTab, setActiveTab] = useState('DASHBOARD');

  // ==========================================================================
  // 1. ÉTAT D'AUTHENTIFICATION JWT (ADMIN / USER)
  // ==========================================================================
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('expensyguard_auth');
      return saved ? JSON.parse(saved) : {
        token: '',
        username: 'admin',
        role: 'admin',
        name: 'Alexandre Dupont (Admin)',
        email: 'admin@expensyguard.com'
      };
    } catch {
      return null;
    }
  });

  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: 'admin', password: 'admin123' });
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState(null);

  // Helper pour injecter les headers d'autorisation JWT
  const authHeaders = useMemo(() => {
    return currentUser?.token ? { 'Authorization': `Bearer ${currentUser.token}` } : {};
  }, [currentUser]);

  // Sauvegarde persistante de la session
  useEffect(() => {
    if (currentUser) {
      localStorage.setItem('expensyguard_auth', JSON.stringify(currentUser));
    } else {
      localStorage.removeItem('expensyguard_auth');
    }
  }, [currentUser]);

  // Initialisation automatique du token admin si non connecté
  useEffect(() => {
    if (!currentUser?.token) {
      handleLogin({ username: 'admin', password: 'admin123' });
    }
  }, []);

  // Gestionnaire de connexion
  const handleLogin = async (overrideUser = null) => {
    setLoginLoading(true);
    setLoginError(null);
    const creds = overrideUser || loginForm;

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      });

      if (res.ok) {
        const data = await res.json();
        setCurrentUser({
          token: data.access_token,
          username: data.user.username,
          role: data.user.role,
          name: data.user.name,
          email: data.user.email,
        });
        setLoginModalOpen(false);
      } else {
        const err = await res.json().catch(() => ({ detail: "Identifiants invalides" }));
        setLoginError(err.detail || "Échec de connexion.");
      }
    } catch (e) {
      setLoginError("Impossible de joindre le serveur FastAPI.");
    } finally {
      setLoginLoading(false);
    }
  };

  // Déconnexion
  const handleLogout = () => {
    setCurrentUser(null);
    setLoginModalOpen(true);
  };

  // ==========================================================================
  // 2. DONNÉES MÉTIERS (REÇUS, KPIS, EMPLOYÉS)
  // ==========================================================================
  const [receipts, setReceipts] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [selectedEmployeeForAudit, setSelectedEmployeeForAudit] = useState('EMP001');

  const [stats, setStats] = useState({
    total_receipts: 0,
    total_spent_eur: 0,
    approved_count: 0,
    review_count: 0,
    rejected_count: 0,
    compliance_rate: 100,
  });

  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Modales
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [imageModalReceipt, setImageModalReceipt] = useState(null);
  const [deleteConfirmReceipt, setDeleteConfirmReceipt] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Fiche employé et filtres temporels
  const [employeeSheetModal, setEmployeeSheetModal] = useState(null);
  const [employeeSheetLoading, setEmployeeSheetLoading] = useState(false);
  const [employeePeriodType, setEmployeePeriodType] = useState('ALL'); // 'ALL', 'YEAR', 'MONTH', 'DAY'
  const [employeeDateValue, setEmployeeDateValue] = useState('');

  // Espace audit
  const [auditFile, setAuditFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isAuditing, setIsAuditing] = useState(false);
  const [latestAuditResult, setLatestAuditResult] = useState(null);
  const [auditError, setAuditError] = useState(null);

  // Récupération des données globales
  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Stats
      const statsRes = await fetch(`${API_BASE_URL}/api/v1/stats`);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      // 2. Reçus
      const receiptsRes = await fetch(`${API_BASE_URL}/api/v1/receipts`);
      if (receiptsRes.ok) {
        const receiptsData = await receiptsRes.json();
        setReceipts(receiptsData);
      }

      // 3. Employés
      const empRes = await fetch(`${API_BASE_URL}/api/v1/employees`);
      if (empRes.ok) {
        const empData = await empRes.json();
        setEmployees(empData);
      }
    } catch (err) {
      console.error("[Frontend] Erreur réseau :", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // ==========================================================================
  // 3. ACTIONS EMPLOYÉS & FILTRES DE FICHE
  // ==========================================================================
  const openEmployeeSheet = async (employeeId, periodType = 'ALL', dateVal = '') => {
    setEmployeeSheetLoading(true);
    setEmployeePeriodType(periodType);
    setEmployeeDateValue(dateVal);

    try {
      let url = `${API_BASE_URL}/api/v1/employees/${employeeId}?period_type=${periodType}`;
      if (dateVal) {
        url += `&date_value=${encodeURIComponent(dateVal)}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setEmployeeSheetModal(data);
      }
    } catch (e) {
      console.error("Erreur fiche employé :", e);
    } finally {
      setEmployeeSheetLoading(false);
    }
  };

  const handlePeriodChange = (newPeriodType, newDateValue = '') => {
    if (!employeeSheetModal?.employee?.id) return;
    openEmployeeSheet(employeeSheetModal.employee.id, newPeriodType, newDateValue);
  };

  // ==========================================================================
  // 4. SUPPRESSION D'UN REÇU (ACTION ADMIN)
  // ==========================================================================
  const handleDeleteReceipt = async (receiptId) => {
    if (!currentUser || currentUser.role !== 'admin') {
      alert("Action refusée : Seul un administrateur peut supprimer un ticket.");
      return;
    }

    setIsDeleting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/receipts/${receiptId}`, {
        method: 'DELETE',
        headers: {
          ...authHeaders,
          'Content-Type': 'application/json',
        },
      });

      if (res.ok) {
        setDeleteConfirmReceipt(null);
        setSelectedReceipt(null);
        setImageModalReceipt(null);
        await fetchData();
        // Si la fiche employé est ouverte, la rafraîchir
        if (employeeSheetModal?.employee?.id) {
          openEmployeeSheet(employeeSheetModal.employee.id, employeePeriodType, employeeDateValue);
        }
      } else {
        const err = await res.json().catch(() => ({ detail: "Échec de suppression" }));
        alert(`Erreur : ${err.detail}`);
      }
    } catch (err) {
      alert("Erreur de communication lors de la suppression.");
    } finally {
      setIsDeleting(false);
    }
  };

  // Mise à jour de statut (Validation / Rejet)
  const handleUpdateStatus = async (receiptId, newStatus) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/receipts/${receiptId}/status`, {
        method: 'PATCH',
        headers: {
          ...authHeaders,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus, note: `Décision de ${currentUser?.name || 'Gestionnaire'}` }),
      });

      if (res.ok) {
        setSelectedReceipt(null);
        await fetchData();
        if (employeeSheetModal?.employee?.id) {
          openEmployeeSheet(employeeSheetModal.employee.id, employeePeriodType, employeeDateValue);
        }
      }
    } catch (err) {
      console.error("Erreur de statut:", err);
    }
  };

  // Téléversement & Audit
  const handleFileSelect = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      setAuditFile(file);
      setAuditError(null);
      setLatestAuditResult(null);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleRunAudit = async () => {
    if (!auditFile) return;

    const formData = new FormData();
    formData.append('file', auditFile);
    formData.append('employee_id', selectedEmployeeForAudit);

    setIsAuditing(true);
    setAuditError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/audit`, {
        method: 'POST',
        headers: authHeaders,
        body: formData,
      });

      if (response.ok) {
        const resultData = await response.json();
        setLatestAuditResult(resultData);
        await fetchData();
      } else {
        const errData = await response.json().catch(() => ({ detail: "Erreur serveur" }));
        setAuditError(errData.detail || "Échec du traitement du reçu.");
      }
    } catch (err) {
      setAuditError("Impossible de joindre le serveur FastAPI.");
    } finally {
      setIsAuditing(false);
    }
  };

  // Filtrage combiné
  const filteredReceipts = receipts.filter((item) => {
    const matchesStatus = filterStatus === 'ALL' || item.status === filterStatus;
    const matchesSearch =
      (item.merchant_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.employee_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.total_amount_ttc || '').includes(searchTerm);
    return matchesStatus && matchesSearch;
  });

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
      {/* ========================================================================= */}
      {/* 1. EN-TÊTE PRINCIPAL & PROFIL JWT                                         */}
      {/* ========================================================================= */}
      <header className="app-header">
        <div className="brand-title">
          <ShieldCheck size={28} color="#2563eb" />
          <span>ExpensyGuard</span>
          <span className="brand-badge">Audit & Collaborateurs</span>
        </div>

        {/* Navigation */}
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

        {/* Espace Utilisateur & Rôle */}
        <div className="user-profile-bar">
          {currentUser ? (
            <div className="user-info-card">
              <div className={`user-role-badge ${currentUser.role === 'admin' ? 'role-admin' : 'role-user'}`}>
                {currentUser.role === 'admin' ? <Crown size={13} /> : <User size={13} />}
                <span>{currentUser.role.toUpperCase()}</span>
              </div>
              <div className="user-details">
                <span className="user-name">{currentUser.name}</span>
              </div>
              <button
                className="btn-icon"
                onClick={() => setLoginModalOpen(true)}
                title="Changer de compte ou basculer de rôle"
              >
                <KeyRound size={15} />
              </button>
              <button
                className="btn-icon btn-logout"
                onClick={handleLogout}
                title="Déconnexion"
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : (
            <button className="btn btn-primary" onClick={() => setLoginModalOpen(true)}>
              <LogIn size={15} />
              Se Connecter
            </button>
          )}

          <button className="btn btn-outline" onClick={fetchData} title="Rafraîchir les données">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
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
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <CheckCircle2 size={12} color="#059669" />
                <span>Tickets validés uniquement</span>
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span>Taux de Conformité</span>
                <TrendingUp size={18} color="#059669" />
              </div>
              <div className="kpi-value">{stats.compliance_rate ?? 100}%</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {stats.approved_count ?? 0} validé(s) / {stats.total_receipts ?? 0} total
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span>Reçus Validés</span>
                <CheckCircle2 size={18} color="#059669" />
              </div>
              <div className="kpi-value">{stats.approved_count ?? 0}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Intégrés dans la comptabilité
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-header">
                <span>À Réviser</span>
                <AlertTriangle size={18} color="#d97706" />
              </div>
              <div className="kpi-value" style={{ color: (stats.review_count ?? 0) > 0 ? '#d97706' : 'inherit' }}>
                {stats.review_count ?? 0}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Nécessitent une validation
              </div>
            </div>
          </section>

          {/* Barre de contrôles et filtres */}
          <div className="controls-bar">
            <div className="search-box">
              <Search size={16} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Rechercher par employé, commerçant ou ID..."
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
                  <th>Employé</th>
                  <th>Commerçant</th>
                  <th>Date</th>
                  <th>Montant TTC</th>
                  <th>Statut</th>
                  <th>Score IA</th>
                  <th>Photo</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredReceipts.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      Aucun reçu trouvé dans la base de données.
                    </td>
                  </tr>
                ) : (
                  filteredReceipts.map((receipt) => (
                    <tr key={receipt.id} onClick={() => setSelectedReceipt(receipt)}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '0.8125rem' }}>
                        {receipt.id}
                      </td>
                      {/* Bouton pour afficher la fiche de l'employé */}
                      <td>
                        <button
                          type="button"
                          className="employee-badge-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            openEmployeeSheet(receipt.employee_id || 'EMP001');
                          }}
                          title="Cliquer pour voir la fiche et les dépenses de l'employé"
                        >
                          <span
                            className="employee-avatar-circle"
                            style={{ backgroundColor: receipt.employee_avatar_color || '#2563eb' }}
                          >
                            {(receipt.employee_name || 'E').substring(0, 2).toUpperCase()}
                          </span>
                          <span className="employee-badge-name">{receipt.employee_name || "Alexandre Martin"}</span>
                        </button>
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
                      <td>
                        <button
                          type="button"
                          className="btn-image-action"
                          onClick={(e) => {
                            e.stopPropagation();
                            setImageModalReceipt(receipt);
                          }}
                          title="Afficher l'image du reçu"
                        >
                          <Eye size={13} />
                          <span>Photo</span>
                        </button>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                          {/* Bouton Supprimer réservé à l'Admin */}
                          {currentUser?.role === 'admin' ? (
                            <button
                              type="button"
                              className="btn-delete-action"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteConfirmReceipt(receipt);
                              }}
                              title="Supprimer ce reçu (Admin)"
                            >
                              <Trash2 size={13} />
                              <span>Supprimer</span>
                            </button>
                          ) : (
                            <span
                              className="delete-locked-badge"
                              title="Suppression réservée à l'administrateur"
                            >
                              <Lock size={12} />
                            </span>
                          )}
                          <ChevronRight size={16} color="var(--text-muted)" />
                        </div>
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

            {/* Sélecteur de l'employé soumettant le reçu */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.4rem', color: 'var(--text-secondary)' }}>
                Collaborateur émetteur de la dépense :
              </label>
              <select
                className="employee-select"
                value={selectedEmployeeForAudit}
                onChange={(e) => setSelectedEmployeeForAudit(e.target.value)}
              >
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} ({emp.department})
                  </option>
                ))}
              </select>
            </div>

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

            {/* Prévisualisation */}
            {previewUrl && (
              <div className="preview-box">
                <img src={previewUrl} alt="Aperçu du ticket" className="preview-image" />
              </div>
            )}

            {/* Bouton de déclenchement */}
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

            {auditError && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', color: '#dc2626', fontSize: '0.8125rem' }}>
                <AlertTriangle size={16} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} />
                {auditError}
              </div>
            )}
          </div>

          {/* Colonne droite : Résultat direct */}
          <div className="audit-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldCheck size={20} color="#059669" />
              Résultat d'Audit en Temps Réel
            </h3>

            {!latestAuditResult && !isAuditing && (
              <div style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--text-muted)' }}>
                <FileText size={48} style={{ margin: '0 auto 1rem auto', opacity: 0.4 }} />
                <p>Sélectionnez un ticket à gauche et lancez l'audit pour observer les règles de gestion et l'affectation à l'employé.</p>
              </div>
            )}

            {isAuditing && (
              <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                <RefreshCw size={36} className="animate-spin" color="#2563eb" style={{ margin: '0 auto 1rem auto' }} />
                <h4 style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Analyse multi-agents en cours</h4>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  OCR $\rightarrow$ IA $\rightarrow$ SIRENE $\rightarrow$ Empreinte $\rightarrow$ Règles budgétaires
                </p>
              </div>
            )}

            {latestAuditResult && !isAuditing && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
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
      {/* MODALE 1 : FICHE EMPLOYÉ AVEC FILTRES TEMPORELS DYNAMIQUES               */}
      {/* ========================================================================= */}
      {employeeSheetModal && (
        <div className="modal-backdrop" onClick={() => setEmployeeSheetModal(null)}>
          <div className="modal-card employee-modal-card" onClick={(e) => e.stopPropagation()}>
            {/* En-tête Fiche Collaborateur */}
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div
                  className="employee-large-avatar"
                  style={{ backgroundColor: employeeSheetModal.employee.avatar_color || '#2563eb' }}
                >
                  {employeeSheetModal.employee.name.substring(0, 2).toUpperCase()}
                </div>
                <div>
                  <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
                    {employeeSheetModal.employee.name}
                  </h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{employeeSheetModal.employee.id}</span>
                    <span>•</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                      <Briefcase size={12} /> {employeeSheetModal.employee.department}
                    </span>
                    <span>•</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                      <Calendar size={12} /> Embauché(e) le {employeeSheetModal.employee.hire_date}
                    </span>
                  </div>
                </div>
              </div>
              <button className="btn btn-outline" onClick={() => setEmployeeSheetModal(null)} style={{ padding: '0.25rem 0.5rem' }}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {/* =================================================================== */}
              {/* BARRE DE FILTRES TEMPORELS (JOUR / MOIS / ANNÉE / TOUT)             */}
              {/* =================================================================== */}
              <div className="employee-filter-bar">
                <div className="filter-title">
                  <Filter size={15} color="var(--accent-primary)" />
                  <span>Période des dépenses :</span>
                </div>

                <div className="filter-period-buttons">
                  <button
                    className={`btn-period ${employeePeriodType === 'ALL' ? 'active' : ''}`}
                    onClick={() => handlePeriodChange('ALL', '')}
                  >
                    Tout l'historique
                  </button>

                  <button
                    className={`btn-period ${employeePeriodType === 'YEAR' ? 'active' : ''}`}
                    onClick={() => handlePeriodChange('YEAR', '2026')}
                  >
                    Année
                  </button>

                  <button
                    className={`btn-period ${employeePeriodType === 'MONTH' ? 'active' : ''}`}
                    onClick={() => handlePeriodChange('MONTH', '2026-10')}
                  >
                    Mois
                  </button>

                  <button
                    className={`btn-period ${employeePeriodType === 'DAY' ? 'active' : ''}`}
                    onClick={() => handlePeriodChange('DAY', new Date().toISOString().split('T')[0])}
                  >
                    Jour
                  </button>
                </div>

                {/* Sélecteur dynamique selon le mode */}
                {employeePeriodType === 'YEAR' && (
                  <div className="period-input-wrapper">
                    <select
                      className="period-select"
                      value={employeeDateValue || '2026'}
                      onChange={(e) => handlePeriodChange('YEAR', e.target.value)}
                    >
                      {['2026', '2025', '2024', '2023', '2022', '2021', '2020'].map((y) => (
                        <option key={y} value={y}>Année {y}</option>
                      ))}
                    </select>
                  </div>
                )}

                {employeePeriodType === 'MONTH' && (
                  <div className="period-input-wrapper">
                    <input
                      type="month"
                      className="period-date-input"
                      value={employeeDateValue || '2026-10'}
                      onChange={(e) => handlePeriodChange('MONTH', e.target.value)}
                    />
                  </div>
                )}

                {employeePeriodType === 'DAY' && (
                  <div className="period-input-wrapper">
                    <input
                      type="date"
                      className="period-date-input"
                      value={employeeDateValue || new Date().toISOString().split('T')[0]}
                      onChange={(e) => handlePeriodChange('DAY', e.target.value)}
                    />
                  </div>
                )}
              </div>

              {/* Indicateurs agrégés pour la période sélectionnée */}
              <div className="employee-kpis-grid">
                <div className="emp-kpi-card highlight">
                  <span className="emp-kpi-label">Total Dépenses Validées</span>
                  <span className="emp-kpi-val">
                    {(employeeSheetModal.stats?.total_spent_eur ?? 0).toFixed(2)} €
                  </span>
                  <span className="emp-kpi-sub">Sur la période sélectionnée</span>
                </div>

                <div className="emp-kpi-card">
                  <span className="emp-kpi-label">Tickets Validés</span>
                  <span className="emp-kpi-val" style={{ color: '#059669' }}>
                    {employeeSheetModal.stats?.approved_count ?? 0}
                  </span>
                  <span className="emp-kpi-sub">Conformes</span>
                </div>

                <div className="emp-kpi-card">
                  <span className="emp-kpi-label">À Réviser</span>
                  <span className="emp-kpi-val" style={{ color: '#d97706' }}>
                    {employeeSheetModal.stats?.review_count ?? 0}
                  </span>
                  <span className="emp-kpi-sub">En attente</span>
                </div>

                <div className="emp-kpi-card">
                  <span className="emp-kpi-label">Rejetés</span>
                  <span className="emp-kpi-val" style={{ color: '#dc2626' }}>
                    {employeeSheetModal.stats?.rejected_count ?? 0}
                  </span>
                  <span className="emp-kpi-sub">Non remboursés</span>
                </div>
              </div>

              {/* Liste des tickets correspondants */}
              <div>
                <h4 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '1rem 0 0.5rem 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Historique des reçus ({employeeSheetModal.receipts?.length || 0})</span>
                  {employeeSheetLoading && <RefreshCw size={14} className="animate-spin" />}
                </h4>

                <div className="employee-receipts-table-wrapper">
                  {employeeSheetModal.receipts?.length === 0 ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                      Aucune dépense enregistrée pour ce collaborateur sur cette période.
                    </div>
                  ) : (
                    <table className="receipts-table small-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Commerçant</th>
                          <th>Date</th>
                          <th>Montant TTC</th>
                          <th>Statut</th>
                          <th>Photo</th>
                          {currentUser?.role === 'admin' && <th>Action</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {employeeSheetModal.receipts.map((r) => (
                          <tr key={r.id}>
                            <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', fontWeight: 600 }}>{r.id}</td>
                            <td>{r.merchant_name}</td>
                            <td>{r.receipt_date}</td>
                            <td style={{ fontWeight: 700 }}>{r.total_amount_ttc} €</td>
                            <td>{renderStatusPill(r.status)}</td>
                            <td>
                              <button
                                type="button"
                                className="btn-image-action"
                                onClick={() => setImageModalReceipt(r)}
                              >
                                <Eye size={12} />
                                <span>Voir</span>
                              </button>
                            </td>
                            {currentUser?.role === 'admin' && (
                              <td>
                                <button
                                  type="button"
                                  className="btn-delete-action"
                                  onClick={() => setDeleteConfirmReceipt(r)}
                                  title="Supprimer définitivement"
                                >
                                  <Trash2 size={12} />
                                </button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>

            <div className="actions-footer">
              <button className="btn btn-primary" onClick={() => setEmployeeSheetModal(null)}>
                Fermer la Fiche
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALE 2 : CONFIRMATION DE SUPPRESSION (ADMIN UNIQUEMENT)                 */}
      {/* ========================================================================= */}
      {deleteConfirmReceipt && (
        <div className="modal-backdrop" onClick={() => setDeleteConfirmReceipt(null)}>
          <div className="modal-card delete-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={{ background: '#fef2f2', padding: '0.5rem', borderRadius: '50%', color: '#dc2626' }}>
                  <Trash2 size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#dc2626' }}>
                    Confirmer la suppression
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Action d'administration irréversible
                  </span>
                </div>
              </div>
              <button className="btn btn-outline" onClick={() => setDeleteConfirmReceipt(null)} style={{ padding: '0.25rem 0.5rem' }}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                Êtes-vous sûr de vouloir supprimer définitivement le reçu <b>#{deleteConfirmReceipt.id}</b> de <b>{deleteConfirmReceipt.merchant_name}</b> ({deleteConfirmReceipt.total_amount_ttc} €) ?
              </p>
              <p style={{ fontSize: '0.8125rem', color: '#dc2626', background: '#fef2f2', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
                ⚠️ Cette action supprimera l'enregistrement de la base de données ainsi que le fichier image correspondant dans <code>data_images/</code>.
              </p>
            </div>

            <div className="actions-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirmReceipt(null)} disabled={isDeleting}>
                Annuler
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleDeleteReceipt(deleteConfirmReceipt.id)}
                disabled={isDeleting}
              >
                {isDeleting ? <RefreshCw size={14} className="animate-spin" /> : <Trash2 size={14} />}
                Supprimer Définitivement
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALE 3 : AUTHENTIFICATION & SÉLECTEUR DE COMPTE (ADMIN / USER)          */}
      {/* ========================================================================= */}
      {loginModalOpen && (
        <div className="modal-backdrop" onClick={() => setLoginModalOpen(false)}>
          <div className="modal-card login-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Shield size={24} color="#2563eb" />
                <div>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Authentification JWT</h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Contrôle d'accès par rôle</span>
                </div>
              </div>
              <button className="btn btn-outline" onClick={() => setLoginModalOpen(false)} style={{ padding: '0.25rem 0.5rem' }}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {/* Boutons d'accès rapide 1-clic pour test instantané */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
                  Connexion rapide pour démonstration :
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <button
                    type="button"
                    className="quick-role-btn role-admin-btn"
                    onClick={() => handleLogin({ username: 'admin', password: 'admin123' })}
                  >
                    <Crown size={18} color="#b45309" />
                    <div>
                      <strong style={{ display: 'block', fontSize: '0.875rem' }}>Compte ADMIN</strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Peut supprimer des reçus</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="quick-role-btn role-user-btn"
                    onClick={() => handleLogin({ username: 'user', password: 'user123' })}
                  >
                    <User size={18} color="#2563eb" />
                    <div>
                      <strong style={{ display: 'block', fontSize: '0.875rem' }}>Compte USER</strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Consultation standard</span>
                    </div>
                  </button>
                </div>
              </div>

              {/* Formulaire manuel */}
              <form onSubmit={(e) => { e.preventDefault(); handleLogin(); }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.25rem' }}>Nom d'utilisateur :</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.5rem 0.75rem', width: '100%' }}
                    value={loginForm.username}
                    onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.25rem' }}>Mot de passe :</label>
                  <input
                    type="password"
                    className="search-input"
                    style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.5rem 0.75rem', width: '100%' }}
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  />
                </div>

                {loginError && (
                  <div style={{ color: '#dc2626', background: '#fef2f2', padding: '0.5rem', borderRadius: '6px', fontSize: '0.8125rem' }}>
                    {loginError}
                  </div>
                )}

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ justifyContent: 'center', marginTop: '0.5rem', padding: '0.65rem' }}
                  disabled={loginLoading}
                >
                  {loginLoading ? <RefreshCw size={16} className="animate-spin" /> : <LogIn size={16} />}
                  Se Connecter avec JWT
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALE 4 : AFFICHAGE DE L'IMAGE DU REÇU                                  */}
      {/* ========================================================================= */}
      {imageModalReceipt && (
        <div className="modal-backdrop" onClick={() => setImageModalReceipt(null)}>
          <div className="modal-card image-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <ImageIcon size={22} color="#2563eb" />
                <div>
                  <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
                    {imageModalReceipt.merchant_name || "Photo du Reçu"}
                  </h2>
                  <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    ID #{imageModalReceipt.id} • {imageModalReceipt.receipt_date || "Date inconnue"}
                  </span>
                </div>
              </div>
              <button className="btn btn-outline" onClick={() => setImageModalReceipt(null)} style={{ padding: '0.25rem 0.5rem' }}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-subtle)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)' }}>
                <div>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Montant TTC : </span>
                  <strong style={{ color: '#2563eb', fontSize: '1.1rem' }}>{imageModalReceipt.total_amount_ttc || "0.00"} €</strong>
                </div>
                <div>
                  {renderStatusPill(imageModalReceipt.status)}
                </div>
              </div>

              <div className="receipt-image-container">
                <img
                  src={`${API_BASE_URL}/api/v1/receipts/${imageModalReceipt.id}/image`}
                  alt={`Reçu ${imageModalReceipt.id}`}
                  className="receipt-modal-image"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                    const fallback = e.currentTarget.parentElement?.querySelector('.image-fallback-box');
                    if (fallback) fallback.style.display = 'flex';
                  }}
                />
                <div className="image-fallback-box" style={{ display: 'none' }}>
                  <FileText size={44} color="#94a3b8" />
                  <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.5rem' }}>Image non disponible</p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Le fichier image n'a pas été trouvé dans le dossier <code>data_images/</code>.
                  </p>
                </div>
              </div>
            </div>

            <div className="actions-footer" style={{ justifyContent: 'space-between' }}>
              <button
                className="btn btn-outline"
                onClick={() => {
                  const r = imageModalReceipt;
                  setImageModalReceipt(null);
                  setSelectedReceipt(r);
                }}
              >
                <FileText size={15} />
                Ouvrir la fiche d'audit complète
              </button>
              <button className="btn btn-primary" onClick={() => setImageModalReceipt(null)}>
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALE 5 : RÉVISION DÉTAILLÉE D'UN REÇU                                  */}
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
                <span className="detail-label">Collaborateur</span>
                <span className="detail-value" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span
                    className="employee-avatar-circle"
                    style={{ backgroundColor: selectedReceipt.employee_avatar_color || '#2563eb', width: '20px', height: '20px', fontSize: '0.65rem' }}
                  >
                    {(selectedReceipt.employee_name || 'E').substring(0, 2).toUpperCase()}
                  </span>
                  {selectedReceipt.employee_name || "Alexandre Martin"} ({selectedReceipt.employee_department || "Général"})
                </span>
              </div>

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
                <span className="detail-label">Photo du ticket</span>
                <button
                  type="button"
                  className="btn-image-action"
                  onClick={() => {
                    const current = selectedReceipt;
                    setSelectedReceipt(null);
                    setImageModalReceipt(current);
                  }}
                >
                  <Eye size={13} />
                  <span>Afficher l'image</span>
                </button>
              </div>

              <div className="detail-row">
                <span className="detail-label">Empreinte SHA-256</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {selectedReceipt.fingerprint ? `${selectedReceipt.fingerprint.substring(0, 16)}...` : "-"}
                </span>
              </div>

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

            <div className="actions-footer" style={{ justifyContent: 'space-between' }}>
              <div>
                {currentUser?.role === 'admin' && (
                  <button
                    className="btn btn-danger"
                    style={{ background: '#fee2e2', color: '#dc2626', borderColor: '#fca5a5' }}
                    onClick={() => {
                      const r = selectedReceipt;
                      setSelectedReceipt(null);
                      setDeleteConfirmReceipt(r);
                    }}
                  >
                    <Trash2 size={15} />
                    Supprimer
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
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
        </div>
      )}
    </div>
  );
}
