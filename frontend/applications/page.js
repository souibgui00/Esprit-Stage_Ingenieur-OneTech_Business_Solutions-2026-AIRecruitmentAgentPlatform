'use client';

import { useState, useEffect } from 'react';
import api from '../../lib/api';
import { 
  Send, 
  Check, 
  X, 
  Settings, 
  Info, 
  AlertTriangle, 
  Loader2, 
  Clock, 
  FileText, 
  User, 
  ExternalLink,
  Camera,
  Terminal,
  FileCheck,
  ChevronDown,
  ChevronUp,
  Copy
} from 'lucide-react';

export default function ApplicationsPage() {
  const [applications, setApplications] = useState([]);
  const [settings, setSettings] = useState({ auto_apply_enabled: false });
  const [loading, setLoading] = useState(true);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('ALL');
  
  // Storing rejection prompts locally for each application
  const [rejectionReasons, setRejectionReasons] = useState({});
  const [showRejectForm, setShowRejectForm] = useState({});
  
  // Toggle proof details accordion per card
  const [expandedProofs, setExpandedProofs] = useState({});
  const [activeProofTab, setActiveProofTab] = useState({});
  const [copiedAppId, setCopiedAppId] = useState(null);
  
  // Loading state per action
  const [actionLoading, setActionLoading] = useState({});

  useEffect(() => {
    async function fetchData() {
      try {
        const [appsRes, settingsRes] = await Promise.all([
          api.get('/applications'),
          api.get('/applications/settings')
        ]);
        setApplications(appsRes.data);
        setSettings(settingsRes.data);
      } catch (err) {
        console.error(err);
        setError("Erreur de chargement des données. Veuillez réessayer.");
      } finally {
        setLoading(false);
        setSettingsLoading(false);
      }
    }
    fetchData();
  }, []);

  // Poll for status updates if any application is processing (status === 'APPROVED')
  useEffect(() => {
    const hasProcessingApps = applications.some(app => app.status === 'APPROVED');
    if (!hasProcessingApps) return;

    const interval = setInterval(async () => {
      try {
        const response = await api.get('/applications');
        setApplications(response.data);
      } catch (err) {
        console.error("Failed to poll applications:", err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [applications]);

  const handleToggleAutoApply = async () => {
    setSettingsLoading(true);
    const newValue = !settings.auto_apply_enabled;
    try {
      const response = await api.put('/applications/settings', {
        auto_apply_enabled: newValue
      });
      setSettings(response.data);
    } catch (err) {
      console.error(err);
      alert("Impossible de mettre à jour les paramètres d'auto-apply.");
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleApprove = async (appId) => {
    setActionLoading(prev => ({ ...prev, [appId]: 'approve' }));
    try {
      const response = await api.post(`/applications/${appId}/approve`);
      setApplications(apps => apps.map(a => a.id === appId ? response.data : a));
      // Auto-expand proof accordion so user sees screenshots & logs immediately!
      setExpandedProofs(prev => ({ ...prev, [appId]: true }));
      setActiveProofTab(prev => ({ ...prev, [appId]: 'screenshots' }));
    } catch (err) {
      console.error(err);
      const errMsg = err.response?.data?.detail || "Une erreur est survenue lors de l'exécution de l'agent web.";
      alert(errMsg);
    } finally {
      setActionLoading(prev => ({ ...prev, [appId]: null }));
    }
  };

  const handleRunAgent = async (appId) => {
    setActionLoading(prev => ({ ...prev, [appId]: 'run_agent' }));
    try {
      const response = await api.post(`/applications/${appId}/run-agent`);
      setApplications(apps => apps.map(a => a.id === appId ? response.data : a));
      setExpandedProofs(prev => ({ ...prev, [appId]: true }));
      setActiveProofTab(prev => ({ ...prev, [appId]: 'screenshots' }));
    } catch (err) {
      console.error(err);
      alert("Une erreur est survenue lors de l'exécution de l'agent web.");
    } finally {
      setActionLoading(prev => ({ ...prev, [appId]: null }));
    }
  };

  const handleReject = async (appId) => {
    const reason = rejectionReasons[appId] || '';
    setActionLoading(prev => ({ ...prev, [appId]: 'reject' }));
    try {
      const response = await api.post(`/applications/${appId}/reject`, {
        reason: reason.trim() || null
      });
      setApplications(apps => apps.map(a => a.id === appId ? response.data : a));
      setShowRejectForm(prev => ({ ...prev, [appId]: false }));
      setRejectionReasons(prev => ({ ...prev, [appId]: '' }));
    } catch (err) {
      console.error(err);
      const errMsg = err.response?.data?.detail || "Une erreur est survenue lors du rejet.";
      alert(errMsg);
    } finally {
      setActionLoading(prev => ({ ...prev, [appId]: null }));
    }
  };

  const toggleProofAccordion = (appId) => {
    setExpandedProofs(prev => ({ ...prev, [appId]: !prev[appId] }));
    if (!activeProofTab[appId]) {
      setActiveProofTab(prev => ({ ...prev, [appId]: 'screenshots' }));
    }
  };

  const handleCopyCoverLetter = (text, appId) => {
    navigator.clipboard.writeText(text);
    setCopiedAppId(appId);
    setTimeout(() => setCopiedAppId(null), 2000);
  };

  const filteredApps = applications.filter(app => {
    if (activeTab === 'ALL') return true;
    return app.status === activeTab;
  });

  const getStatusBadgeStyles = (status) => {
    switch (status) {
      case 'PENDING_VALIDATION':
        return { bg: 'rgba(245, 158, 11, 0.1)', text: 'var(--warning)', label: 'En attente' };
      case 'APPROVED':
        return { bg: 'rgba(108, 99, 255, 0.1)', text: 'var(--primary)', label: "Agent Web en cours..." };
      case 'SENT':
        return { bg: 'rgba(16, 185, 129, 0.1)', text: 'var(--success)', label: 'Traitée / Envoyée' };
      case 'FAILED':
        return { bg: 'rgba(239, 68, 68, 0.1)', text: 'var(--error)', label: 'Échouée' };
      case 'REJECTED':
        return { bg: 'rgba(255, 255, 255, 0.05)', text: 'var(--text-secondary)', label: 'Rejetée' };
      case 'MANUAL_REQUIRED':
        return { bg: 'rgba(245, 158, 11, 0.1)', text: 'var(--warning)', label: 'Action requise' };
      default:
        return { bg: 'rgba(255, 255, 255, 0.05)', text: 'var(--text-primary)', label: status };
    }
  };

  const getModeLabel = (mode) => {
    return mode === 'FULL_AUTO' ? 'Auto-apply' : 'Validation humaine';
  };

  return (
    <main className="container">
        {/* Page Header */}
        <div style={{ marginBottom: '2.5rem', marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 className="gradient-text" style={{ fontSize: '2.2rem', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Send size={28} style={{ color: 'var(--primary)' }} />
              Suivi des candidatures & Agent Web
            </h1>
            <p style={{ color: 'var(--text-secondary)' }}>
              Consultez les actions autonomes de l'Agent Web (Playwright), examinez les captures d'écran et suivez vos candidatures.
            </p>
          </div>

          {/* Auto Apply Settings Box */}
          <div className="glass-card" style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1.25rem 1.5rem',
            background: 'var(--bg-secondary)',
            border: '1px solid rgba(108, 99, 255, 0.15)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{
                background: settings.auto_apply_enabled ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                color: settings.auto_apply_enabled ? 'var(--success)' : 'var(--text-muted)',
                padding: '0.75rem',
                borderRadius: '10px',
                display: 'flex'
              }}>
                <Settings size={22} className={settingsLoading ? 'animate-spin' : ''} style={{ animation: settingsLoading ? 'spin 2s linear infinite' : 'none' }} />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Mode Auto-apply</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {settings.auto_apply_enabled 
                    ? 'Les candidatures validées sont envoyées automatiquement par l\'agent' 
                    : 'Chaque candidature nécessite votre validation avant envoi'}
                </div>
              </div>
            </div>
            <button
              onClick={handleToggleAutoApply}
              disabled={settingsLoading}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
                background: settings.auto_apply_enabled ? 'var(--success)' : 'var(--bg-tertiary)',
                color: settings.auto_apply_enabled ? '#0b0a16' : 'var(--text-primary)',
                cursor: settingsLoading ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: '0.85rem',
                transition: 'all var(--transition-fast)'
              }}
            >
              {settings.auto_apply_enabled ? 'Activé' : 'Désactivé'}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ 
          display: 'flex', 
          gap: '0.5rem', 
          marginBottom: '2rem', 
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '0.5rem',
          overflowX: 'auto'
        }}>
          {['ALL', 'PENDING_VALIDATION', 'APPROVED', 'SENT', 'FAILED', 'REJECTED'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                border: 'none',
                background: activeTab === tab ? 'var(--primary-glow)' : 'transparent',
                color: activeTab === tab ? 'var(--primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.9rem',
                whiteSpace: 'nowrap',
                transition: 'all var(--transition-fast)'
              }}
            >
              {tab === 'ALL' ? 'Toutes' : getStatusBadgeStyles(tab).label}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
            <Loader2 size={32} className="animate-spin" style={{ marginBottom: '1rem' }} />
            <p>Chargement des candidatures...</p>
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--error)' }}>
            <AlertTriangle size={48} style={{ marginBottom: '1rem' }} />
            <p>{error}</p>
          </div>
        ) : filteredApps.length === 0 ? (
          <div className="glass-card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
            <Send size={48} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
            <h3 style={{ fontSize: '1.4rem', marginBottom: '0.5rem' }}>Aucune candidature</h3>
            <p style={{ color: 'var(--text-secondary)' }}>
              {activeTab === 'ALL' 
                ? 'Vous n\'avez pas encore de candidatures. Allez sur la page Matching pour en créer.'
                : `Aucune candidature avec le statut: ${getStatusBadgeStyles(activeTab).label}`}
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {filteredApps.map(app => (
              <div key={app.id} className="glass-card" style={{ padding: '1.5rem' }}>
                {/* Header */}
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'flex-start', 
                  marginBottom: '1rem',
                  flexWrap: 'wrap',
                  gap: '1rem'
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                      <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>
                        {app.job_offer?.title || 'Offre sans titre'}
                      </h3>
                      <span style={{
                        padding: '0.2rem 0.6rem',
                        borderRadius: '20px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background: getStatusBadgeStyles(app.status).bg,
                        color: getStatusBadgeStyles(app.status).text
                      }}>
                        {getStatusBadgeStyles(app.status).label}
                      </span>
                      <span style={{
                        padding: '0.2rem 0.6rem',
                        borderRadius: '20px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background: 'rgba(255, 255, 255, 0.05)',
                        color: 'var(--text-secondary)'
                      }}>
                        {getModeLabel(app.mode)}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      {app.job_offer?.company} • {app.job_offer?.location}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    {app.job_offer?.source_url && (
                      <a 
                        href={app.job_offer.source_url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          padding: '0.4rem 0.8rem',
                          borderRadius: '8px',
                          border: '1px solid var(--border-color)',
                          background: 'transparent',
                          color: 'var(--text-secondary)',
                          textDecoration: 'none',
                          fontSize: '0.85rem',
                          transition: 'all var(--transition-fast)'
                        }}
                      >
                        <ExternalLink size={14} />
                        Offre
                      </a>
                    )}
                  </div>
                </div>

                {/* Actions based on status */}
                {app.status === 'PENDING_VALIDATION' && (
                  <div style={{ 
                    display: 'flex', 
                    gap: '0.75rem', 
                    marginBottom: '1rem',
                    flexWrap: 'wrap'
                  }}>
                    <button
                      onClick={() => handleApprove(app.id)}
                      disabled={actionLoading[app.id] === 'approve'}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.6rem 1.2rem',
                        borderRadius: '8px',
                        border: 'none',
                        background: 'var(--success)',
                        color: '#0b0a16',
                        cursor: actionLoading[app.id] === 'approve' ? 'not-allowed' : 'pointer',
                        fontWeight: 600,
                        fontSize: '0.9rem',
                        transition: 'all var(--transition-fast)'
                      }}
                    >
                      {actionLoading[app.id] === 'approve' ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Validation...
                        </>
                      ) : (
                        <>
                          <Check size={16} />
                          Valider
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => setShowRejectForm(prev => ({ ...prev, [app.id]: !prev[app.id] }))}
                      disabled={actionLoading[app.id] === 'reject'}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.6rem 1.2rem',
                        borderRadius: '8px',
                        border: '1px solid var(--border-color)',
                        background: 'transparent',
                        color: 'var(--error)',
                        cursor: actionLoading[app.id] === 'reject' ? 'not-allowed' : 'pointer',
                        fontWeight: 600,
                        fontSize: '0.9rem',
                        transition: 'all var(--transition-fast)'
                      }}
                    >
                      {actionLoading[app.id] === 'reject' ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Rejet...
                        </>
                      ) : (
                        <>
                          <X size={16} />
                          Rejeter
                        </>
                      )}
                    </button>
                  </div>
                )}

                {showRejectForm[app.id] && (
                  <div style={{ marginBottom: '1rem' }}>
                    <textarea
                      value={rejectionReasons[app.id] || ''}
                      onChange={(e) => setRejectionReasons(prev => ({ ...prev, [app.id]: e.target.value }))}
                      placeholder="Raison du rejet (optionnel)..."
                      style={{
                        width: '100%',
                        padding: '0.75rem',
                        borderRadius: '8px',
                        border: '1px solid var(--border-color)',
                        background: 'rgba(255, 255, 255, 0.03)',
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-family)',
                        fontSize: '0.9rem',
                        minHeight: '80px',
                        resize: 'vertical',
                        marginBottom: '0.5rem'
                      }}
                    />
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => handleReject(app.id)}
                        disabled={actionLoading[app.id] === 'reject'}
                        style={{
                          padding: '0.5rem 1rem',
                          borderRadius: '6px',
                          border: 'none',
                          background: 'var(--error)',
                          color: '#ffffff',
                          cursor: actionLoading[app.id] === 'reject' ? 'not-allowed' : 'pointer',
                          fontWeight: 600,
                          fontSize: '0.85rem'
                        }}
                      >
                        Confirmer le rejet
                      </button>
                      <button
                        onClick={() => {
                          setShowRejectForm(prev => ({ ...prev, [app.id]: false }));
                          setRejectionReasons(prev => ({ ...prev, [app.id]: '' }));
                        }}
                        style={{
                          padding: '0.5rem 1rem',
                          borderRadius: '6px',
                          border: '1px solid var(--border-color)',
                          background: 'transparent',
                          color: 'var(--text-secondary)',
                          cursor: 'pointer',
                          fontWeight: 600,
                          fontSize: '0.85rem'
                        }}
                      >
                        Annuler
                      </button>
                    </div>
                  </div>
                )}

                {app.status === 'MANUAL_REQUIRED' && (
                  <div style={{ marginBottom: '1rem' }}>
                    <button
                      onClick={() => handleRunAgent(app.id)}
                      disabled={actionLoading[app.id] === 'run_agent'}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.6rem 1.2rem',
                        borderRadius: '8px',
                        border: 'none',
                        background: 'var(--primary)',
                        color: '#ffffff',
                        cursor: actionLoading[app.id] === 'run_agent' ? 'not-allowed' : 'pointer',
                        fontWeight: 600,
                        fontSize: '0.9rem',
                        transition: 'all var(--transition-fast)'
                      }}
                    >
                      {actionLoading[app.id] === 'run_agent' ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Exécution...
                        </>
                      ) : (
                        <>
                          <Settings size={16} />
                          Relancer l'agent
                        </>
                      )}
                    </button>
                  </div>
                )}

                {/* Cover Letter */}
                {app.cover_letter && (
                  <div style={{ 
                    padding: '1rem', 
                    background: 'rgba(255, 255, 255, 0.02)', 
                    borderRadius: '8px', 
                    marginBottom: '1rem',
                    border: '1px solid var(--border-color)'
                  }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      marginBottom: '0.5rem' 
                    }}>
                      <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                        Lettre de motivation générée
                      </span>
                      <button
                        onClick={() => handleCopyCoverLetter(app.cover_letter, app.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          padding: '0.3rem 0.6rem',
                          borderRadius: '6px',
                          border: '1px solid var(--border-color)',
                          background: 'transparent',
                          color: 'var(--text-secondary)',
                          cursor: 'pointer',
                          fontSize: '0.8rem',
                          transition: 'all var(--transition-fast)'
                        }}
                      >
                        {copiedAppId === app.id ? <Check size={14} /> : <Copy size={14} />}
                        {copiedAppId === app.id ? 'Copié' : 'Copier'}
                      </button>
                    </div>
                    <div style={{ 
                      fontSize: '0.9rem', 
                      color: 'var(--text-secondary)', 
                      lineHeight: '1.6',
                      maxHeight: '150px',
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {app.cover_letter}
                    </div>
                  </div>
                )}

                {/* Proof accordion (screenshots & logs) */}
                {(app.screenshots?.length > 0 || app.logs) && (
                  <div>
                    <button
                      onClick={() => toggleProofAccordion(app.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.5rem 0',
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-secondary)',
                        cursor: 'pointer',
                        fontSize: '0.9rem',
                        fontWeight: 500,
                        width: '100%',
                        justifyContent: 'flex-start'
                      }}
                    >
                      {expandedProofs[app.id] ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      Preuves d'exécution ({app.screenshots?.length || 0} captures)
                    </button>

                    {expandedProofs[app.id] && (
                      <div style={{ marginTop: '1rem' }}>
                        {/* Tabs */}
                        <div style={{ 
                          display: 'flex', 
                          gap: '0.5rem', 
                          marginBottom: '1rem',
                          borderBottom: '1px solid var(--border-color)',
                          paddingBottom: '0.5rem'
                        }}>
                          <button
                            onClick={() => setActiveProofTab(prev => ({ ...prev, [app.id]: 'screenshots' }))}
                            style={{
                              padding: '0.4rem 0.8rem',
                              borderRadius: '6px',
                              border: 'none',
                              background: activeProofTab[app.id] === 'screenshots' ? 'var(--primary-glow)' : 'transparent',
                              color: activeProofTab[app.id] === 'screenshots' ? 'var(--primary)' : 'var(--text-secondary)',
                              cursor: 'pointer',
                              fontSize: '0.85rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem'
                            }}
                          >
                            <Camera size={14} />
                            Captures
                          </button>
                          <button
                            onClick={() => setActiveProofTab(prev => ({ ...prev, [app.id]: 'logs' }))}
                            style={{
                              padding: '0.4rem 0.8rem',
                              borderRadius: '6px',
                              border: 'none',
                              background: activeProofTab[app.id] === 'logs' ? 'var(--primary-glow)' : 'transparent',
                              color: activeProofTab[app.id] === 'logs' ? 'var(--primary)' : 'var(--text-secondary)',
                              cursor: 'pointer',
                              fontSize: '0.85rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.35rem'
                            }}
                          >
                            <Terminal size={14} />
                            Logs
                          </button>
                        </div>

                        {/* Screenshots */}
                        {activeProofTab[app.id] === 'screenshots' && app.screenshots?.length > 0 && (
                          <div style={{ 
                            display: 'grid', 
                            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', 
                            gap: '1rem' 
                          }}>
                            {app.screenshots.map((screenshot, idx) => (
                              <div key={idx} style={{ position: 'relative' }}>
                                <img
                                  src={screenshot}
                                  alt={`Capture ${idx + 1}`}
                                  style={{
                                    width: '100%',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border-color)'
                                  }}
                                />
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Logs */}
                        {activeProofTab[app.id] === 'logs' && app.logs && (
                          <div style={{
                            padding: '1rem',
                            background: 'rgba(0, 0, 0, 0.3)',
                            borderRadius: '8px',
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            color: 'var(--text-secondary)',
                            maxHeight: '300px',
                            overflow: 'auto',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word'
                          }}>
                            {app.logs}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Failure reason */}
                {app.status === 'FAILED' && app.failure_reason && (
                  <div style={{
                    padding: '0.75rem',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid var(--error)',
                    borderRadius: '8px',
                    marginTop: '1rem',
                    fontSize: '0.85rem',
                    color: 'var(--error)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', fontWeight: 600 }}>
                      <AlertTriangle size={14} />
                      Échec
                    </div>
                    {app.failure_reason}
                  </div>
                )}

                {/* Rejection reason */}
                {app.status === 'REJECTED' && app.rejection_reason && (
                  <div style={{
                    padding: '0.75rem',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    marginTop: '1rem',
                    fontSize: '0.85rem',
                    color: 'var(--text-secondary)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', fontWeight: 600 }}>
                      <X size={14} />
                      Raison du rejet
                    </div>
                    {app.rejection_reason}
                  </div>
                )}

                {/* Timestamp */}
                <div style={{ 
                  marginTop: '1rem', 
                  paddingTop: '1rem', 
                  borderTop: '1px solid var(--border-color)',
                  fontSize: '0.8rem', 
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem'
                }}>
                  <Clock size={12} />
                  Créée le {new Date(app.created_at).toLocaleString('fr-FR')}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
  );
}
