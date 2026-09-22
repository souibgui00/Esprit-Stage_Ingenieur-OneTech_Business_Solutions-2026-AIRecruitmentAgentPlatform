'use client';

import { useState, useEffect } from 'react';
import { X, FileText, Sparkles, Save, RefreshCw, AlertTriangle, ExternalLink, Clock, CheckCircle2, XCircle, Camera, Send, HelpCircle } from 'lucide-react';
import { applicationsApi } from '../lib/api/applications';


export default function ApplicationDetailModal({ application, onClose, onUpdate }) {
  const [loading, setLoading] = useState(false);
  const [coverLetter, setCoverLetter] = useState(application?.cover_letter || '');
  const [editingCoverLetter, setEditingCoverLetter] = useState(false);
  const [generatingCoverLetter, setGeneratingCoverLetter] = useState(false);
  const [actionDetails, setActionDetails] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setCoverLetter(application?.cover_letter || '');
    setEditingCoverLetter(false);
    setError('');
  }, [application]);

  // Load action details if status is ACTION_REQUIRED or MANUAL_REQUIRED
  useEffect(() => {
    if (application?.status === 'ACTION_REQUIRED' || application?.status === 'MANUAL_REQUIRED') {
      loadActionDetails();
    } else {
      setActionDetails(null);
    }
  }, [application]);

  const loadActionDetails = async () => {
    try {
      const details = await applicationsApi.getActionDetails(application.id);
      setActionDetails(details);
    } catch (err) {
      console.error('Failed to load action details:', err);
    }
  };

  const handleGenerateCoverLetter = async () => {
    setGeneratingCoverLetter(true);
    setError('');
    try {
      const result = await applicationsApi.generateCoverLetter(application.id);
      setCoverLetter(result.cover_letter);
      setEditingCoverLetter(true);
      if (onUpdate) onUpdate(result);
    } catch (err) {
      setError('Failed to generate cover letter. Please try again.');
    } finally {
      setGeneratingCoverLetter(false);
    }
  };

  const handleSaveCoverLetter = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await applicationsApi.updateCoverLetter(application.id, coverLetter);
      setEditingCoverLetter(false);
      if (onUpdate) onUpdate(result);
    } catch (err) {
      setError('Failed to save cover letter. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const [answers, setAnswers] = useState({});
  const [submittingAnswers, setSubmittingAnswers] = useState(false);

  const handleRetry = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await applicationsApi.runAgent(application.id);
      if (onUpdate) onUpdate(result);
    } catch (err) {
      setError('Failed to retry submission. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerChange = (fieldId, value) => {
    setAnswers((prev) => ({
      ...prev,
      [fieldId]: value,
    }));
  };

  const handleSubmitAnswers = async (e) => {
    e?.preventDefault();
    setSubmittingAnswers(true);
    setError('');
    try {
      const result = await applicationsApi.answerQuestions(application.id, answers);
      if (onUpdate) onUpdate(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to submit answers and resume application.');
    } finally {
      setSubmittingAnswers(false);
    }
  };


  const formatDate = (d) =>
    d
      ? new Intl.DateTimeFormat(undefined, {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }).format(new Date(d))
      : '';

  if (!application) return null;

  const jobTitle = application.match_details?.job_title || 'Job';
  const company = application.match_details?.company || 'Company';
  const jobUrl = actionDetails?.job_offer_url || application.match_details?.job_offer_url;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px', maxHeight: '90vh', overflowY: 'auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: '20px', fontWeight: 800, margin: '0 0 8px', color: 'var(--ink)' }}>
              {jobTitle}
            </h2>
            <p style={{ fontSize: '14px', color: 'var(--muted)', margin: 0 }}>{company}</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}>
            <X size={20} style={{ color: 'var(--muted)' }} />
          </button>
        </div>

        {error && (
          <div style={{
            background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: '8px',
            padding: '12px', marginBottom: '16px', fontSize: '13px', color: '#9f1239'
          }}>
            <AlertTriangle size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
            {error}
          </div>
        )}

        {/* Status & Mode */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
          <div style={{ background: 'var(--soft)', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', fontWeight: 600 }}>
            <span style={{ color: 'var(--muted)' }}>Mode:</span> {application.mode}
          </div>
          <div style={{ background: 'var(--soft)', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', fontWeight: 600 }}>
            <span style={{ color: 'var(--muted)' }}>Status:</span> {application.status}
          </div>
        </div>

        {/* Dates */}
        <div style={{ fontSize: '13px', color: 'var(--muted)', marginBottom: '20px' }}>
          <div>Created: {formatDate(application.created_at)}</div>
          {application.submitted_at && <div>Submitted: {formatDate(application.submitted_at)}</div>}
        </div>

        {/* ACTION_REQUIRED Section */}
        {(application.status === 'ACTION_REQUIRED' || application.status === 'MANUAL_REQUIRED') && actionDetails && (
          <div style={{
            background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '10px',
            padding: '18px', marginBottom: '20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <AlertTriangle size={18} style={{ color: '#ea580c' }} />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#c2410c' }}>
                Action Required
              </h3>
            </div>
            <p style={{ fontSize: '14px', color: '#9a3412', margin: '0 0 16px', lineHeight: 1.5 }}>
              {actionDetails.action_reason || 'Des informations complémentaires sont nécessaires pour finaliser cette candidature.'}
            </p>

            {/* Interactive Questions Form */}
            {actionDetails.pending_questions && actionDetails.pending_questions.length > 0 ? (
              <form onSubmit={handleSubmitAnswers} style={{ marginBottom: '16px' }}>
                <div style={{
                  background: '#ffffff',
                  border: '1px solid #fed7aa',
                  borderRadius: '8px',
                  padding: '16px',
                  marginBottom: '16px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
                    <HelpCircle size={16} style={{ color: '#c2410c' }} />
                    <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#9a3412', margin: 0 }}>
                      Veuillez répondre aux questions ci-dessous pour continuer la soumission automatique :
                    </h4>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {actionDetails.pending_questions.map((q) => {
                      const qId = q.id;
                      const qType = q.type || 'text';
                      const isReq = q.required !== false;
                      const curVal = answers[qId] !== undefined ? answers[qId] : '';

                      return (
                        <div key={qId} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <label style={{ fontSize: '13px', fontWeight: 600, color: '#374151' }}>
                            {q.label}
                            {isReq && <span style={{ color: '#dc2626', marginLeft: '4px' }}>*</span>}
                          </label>

                          {qType === 'select' ? (
                            <select
                              value={curVal}
                              required={isReq}
                              onChange={(e) => handleAnswerChange(qId, e.target.value)}
                              style={{
                                padding: '8px 12px',
                                borderRadius: '6px',
                                border: '1px solid #d1d5db',
                                fontSize: '13px',
                                background: '#fff'
                              }}
                            >
                              <option value="">-- Sélectionnez une option --</option>
                              {q.options && q.options.map((opt, idx) => {
                                const optVal = typeof opt === 'object' ? opt.value : opt;
                                const optLabel = typeof opt === 'object' ? opt.label : opt;
                                return (
                                  <option key={idx} value={optVal}>{optLabel}</option>
                                );
                              })}
                            </select>
                          ) : qType === 'radio' ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '2px' }}>
                              {q.options && q.options.map((opt, idx) => {
                                const optVal = typeof opt === 'object' ? opt.value : opt;
                                const optLabel = typeof opt === 'object' ? opt.label : opt;
                                return (
                                  <label key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={qId}
                                      value={optVal}
                                      checked={curVal === optVal}
                                      required={isReq && !curVal}
                                      onChange={() => handleAnswerChange(qId, optVal)}
                                    />
                                    <span>{optLabel}</span>
                                  </label>
                                );
                              })}
                            </div>
                          ) : qType === 'textarea' ? (
                            <textarea
                              value={curVal}
                              required={isReq}
                              rows={3}
                              onChange={(e) => handleAnswerChange(qId, e.target.value)}
                              placeholder={`Votre réponse...`}
                              style={{
                                padding: '8px 12px',
                                borderRadius: '6px',
                                border: '1px solid #d1d5db',
                                fontSize: '13px',
                                resize: 'vertical',
                                fontFamily: 'inherit'
                              }}
                            />
                          ) : (
                            <input
                              type="text"
                              value={curVal}
                              required={isReq}
                              onChange={(e) => handleAnswerChange(qId, e.target.value)}
                              placeholder={`Votre réponse...`}
                              style={{
                                padding: '8px 12px',
                                borderRadius: '6px',
                                border: '1px solid #d1d5db',
                                fontSize: '13px'
                              }}
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <button
                    type="submit"
                    disabled={submittingAnswers}
                    className="button primary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '13px',
                      padding: '10px 20px',
                      background: '#ea580c',
                      borderColor: '#ea580c'
                    }}
                  >
                    {submittingAnswers ? (
                      <><RefreshCw size={14} className="disc-spin" /> Soumission en cours...</>
                    ) : (
                      <><Send size={14} /> Valider et Soumettre la Candidature</>
                    )}
                  </button>

                  {jobUrl && (
                    <a
                      href={jobUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontSize: '12px', color: '#9a3412', textDecoration: 'underline', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                    >
                      <ExternalLink size={12} /> Ou ouvrir manuellement l'offre externe
                    </a>
                  )}
                </div>
              </form>
            ) : (
              jobUrl && (
                <div style={{ marginBottom: '16px' }}>
                  <a
                    href={jobUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="button primary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', padding: '8px 16px' }}
                  >
                    <ExternalLink size={14} /> Ouvrir la page de l'offre
                  </a>
                </div>
              )
            )}

            {actionDetails.screenshots && Object.keys(actionDetails.screenshots).length > 0 && (
              <div style={{ marginTop: '14px', borderTop: '1px dashed #fed7aa', paddingTop: '12px' }}>
                <p style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: '#9a3412' }}>
                  Captures d'écran de l'étape bloquante :
                </p>
                {Object.entries(actionDetails.screenshots).map(([key, url]) => (
                  <div key={key} style={{ marginBottom: '8px' }}>
                    <img
                      src={url}
                      alt={key}
                      style={{ maxWidth: '100%', borderRadius: '6px', border: '1px solid #fed7aa' }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}


        {/* Screenshots Section - for any application with screenshots */}
        {application.screenshots && Object.keys(application.screenshots).length > 0 && (
          <div style={{
            background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px',
            padding: '16px', marginBottom: '20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Camera size={18} style={{ color: '#166534' }} />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#15803d' }}>
                Application Screenshots
              </h3>
            </div>
            <div style={{ marginTop: '12px' }}>
              {Object.entries(application.screenshots).map(([key, url]) => (
                <div key={key} style={{ marginBottom: '12px' }}>
                  <p style={{ fontSize: '12px', fontWeight: 600, marginBottom: '4px', color: '#166534' }}>
                    {key}
                  </p>
                  <img
                    src={url}
                    alt={key}
                    style={{ maxWidth: '100%', borderRadius: '6px', border: '1px solid #bbf7d0' }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Failure Reason */}
        {application.status === 'FAILED' && application.failure_reason && (
          <div style={{
            background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: '10px',
            padding: '16px', marginBottom: '20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <XCircle size={18} style={{ color: '#dc2626' }} />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#991b1b' }}>
                Submission Failed
              </h3>
            </div>
            <p style={{ fontSize: '14px', color: '#b91c1c', margin: 0, lineHeight: 1.5 }}>
              {application.failure_reason}
            </p>
          </div>
        )}

        {/* Cover Letter Section */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={16} /> Cover Letter
            </h3>
            {!editingCoverLetter && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={handleGenerateCoverLetter}
                  disabled={generatingCoverLetter || ['SENT', 'FAILED', 'REJECTED'].includes(application.status)}
                  className="button secondary"
                  style={{ fontSize: '12px', padding: '6px 12px' }}
                >
                  {generatingCoverLetter ? (
                    <><RefreshCw size={12} className="disc-spin" /> Generating...</>
                  ) : (
                    <><Sparkles size={12} /> Generate</>
                  )}
                </button>
                {coverLetter && ['PENDING_VALIDATION', 'APPROVED', 'ACTION_REQUIRED', 'MANUAL_REQUIRED'].includes(application.status) && (
                  <button
                    onClick={() => setEditingCoverLetter(true)}
                    className="button secondary"
                    style={{ fontSize: '12px', padding: '6px 12px' }}
                  >
                    Edit
                  </button>
                )}
              </div>
            )}
          </div>

          {editingCoverLetter ? (
            <div>
              <textarea
                value={coverLetter}
                onChange={(e) => setCoverLetter(e.target.value)}
                style={{
                  width: '100%',
                  minHeight: '200px',
                  padding: '12px',
                  border: '1.5px solid var(--line)',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                  boxSizing: 'border-box'
                }}
                placeholder="Write your cover letter..."
              />
              <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                <button
                  onClick={handleSaveCoverLetter}
                  disabled={loading}
                  className="button primary"
                  style={{ fontSize: '13px', padding: '8px 16px' }}
                >
                  {loading ? <><RefreshCw size={12} className="disc-spin" /> Saving...</> : <><Save size={12} /> Save</>}
                </button>
                <button
                  onClick={() => {
                    setCoverLetter(application?.cover_letter || '');
                    setEditingCoverLetter(false);
                  }}
                  className="button secondary"
                  style={{ fontSize: '13px', padding: '8px 16px' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{
              background: 'var(--soft)', borderRadius: '8px', padding: '16px',
              minHeight: '100px', fontSize: '14px', lineHeight: 1.6, color: 'var(--ink)',
              whiteSpace: 'pre-wrap'
            }}>
              {coverLetter || <span style={{ color: 'var(--muted)' }}>No cover letter generated yet.</span>}
            </div>
          )}
        </div>

        {/* Retry Button for FAILED */}
        {application.status === 'FAILED' && (
          <button
            onClick={handleRetry}
            disabled={loading}
            className="button primary"
            style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
          >
            {loading ? <><RefreshCw size={14} className="disc-spin" /> Retrying...</> : <><RefreshCw size={14} /> Retry Submission</>}
          </button>
        )}

        {/* Execution Logs (expandable) */}
        {application.execution_logs && (
          <details style={{ marginTop: '20px' }}>
            <summary style={{ cursor: 'pointer', fontSize: '13px', fontWeight: 600, color: 'var(--muted)' }}>
              Execution Logs
            </summary>
            <pre style={{
              background: '#1e1e1e', color: '#d4d4d4', padding: '12px', borderRadius: '6px',
              fontSize: '12px', overflowX: 'auto', marginTop: '8px'
            }}>
              {JSON.stringify(application.execution_logs, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
