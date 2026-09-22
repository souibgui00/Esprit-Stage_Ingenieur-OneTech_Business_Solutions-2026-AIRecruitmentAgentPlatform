'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import CandidateShell from '../../components/layout/CandidateShell';
import { applicationsApi } from '../../lib/api/applications';
import { EmptyState, ErrorState, LoadingState, StatusBadge, MatchScore } from '../../components/ui';
import { ExternalLink, ArrowRight, CheckCircle2, X, FileText, AlertTriangle, RefreshCw, Eye } from 'lucide-react';
import ApplicationDetailModal from '../../components/ApplicationDetailModal';

const formatDate = (d) =>
  d
    ? new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      }).format(new Date(d))
    : '';

const statusDescription = {
  DRAFT: 'Draft application - not yet submitted',
  PENDING_VALIDATION: 'Waiting for your approval',
  APPROVED: 'Approved and waiting for submission',
  SUBMITTING: 'Application is being submitted',
  SENT: 'Application submitted successfully',
  FAILED: 'Submission failed',
  ACTION_REQUIRED: 'Your action is required to continue',
  MANUAL_REQUIRED: 'Your action is required to continue',
  REJECTED: 'Application rejected by you',
};

export default function Applications() {
  const [apps, setApps] = useState(null);
  const [error, setError] = useState('');
  const [selectedApp, setSelectedApp] = useState(null);
  const [loadingId, setLoadingId] = useState(null);
  const [pollingIds, setPollingIds] = useState(new Set());

  // Load applications
  useEffect(() => {
    loadApplications();
  }, []);

  // Poll for SUBMITTING applications
  useEffect(() => {
    if (pollingIds.size === 0) return;

    const interval = setInterval(async () => {
      try {
        const updatedApps = await applicationsApi.list();
        setApps(updatedApps);
        
        // Check if any SUBMITTING apps have reached terminal state
        const stillSubmitting = updatedApps
          .filter(app => app.status === 'SUBMITTING')
          .map(app => app.id);
        
        setPollingIds(new Set(stillSubmitting));
      } catch (err) {
        console.error('Polling failed:', err);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [pollingIds]);

  const loadApplications = async () => {
    try {
      const data = await applicationsApi.list();
      setApps(data);
      
      // Start polling for SUBMITTING apps
      const submittingIds = data
        .filter(app => app.status === 'SUBMITTING')
        .map(app => app.id);
      setPollingIds(new Set(submittingIds));
    } catch (err) {
      setError('We could not load your applications.');
    }
  };

  const handleApprove = async (appId) => {
    setLoadingId(appId);
    setError('');
    try {
      const updated = await applicationsApi.approve(appId);
      setApps(prev => prev.map(app => app.id === appId ? updated : app));
      
      // Start polling if status becomes SUBMITTING
      if (updated.status === 'SUBMITTING') {
        setPollingIds(prev => new Set([...prev, appId]));
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve application.');
    } finally {
      setLoadingId(null);
    }
  };

  const handleReject = async (appId) => {
    const reason = prompt('Reason for rejection (optional):');
    setLoadingId(appId);
    setError('');
    try {
      const updated = await applicationsApi.reject(appId, reason);
      setApps(prev => prev.map(app => app.id === appId ? updated : app));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject application.');
    } finally {
      setLoadingId(null);
    }
  };

  const canApprove = (app) => app.status === 'PENDING_VALIDATION';
  const canReject = (app) => app.status === 'PENDING_VALIDATION';
  const isSubmitting = (app) => app.status === 'SUBMITTING';
  const isActionRequired = (app) => app.status === 'ACTION_REQUIRED' || app.status === 'MANUAL_REQUIRED';

  return (
    <CandidateShell>
      <div className="page disc-page">
        <div className="disc-header disc-enter">
          <p className="eyebrow">My Applications</p>
          <h1 className="disc-title">Tracked Opportunities</h1>
          <p className="disc-subtitle">
            Manage and track your application workflow and calculated match scores.
          </p>
        </div>

        {error && (
          <div className="disc-error disc-enter">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        <section className="section card disc-enter disc-enter--1">
          {!apps ? (
            <LoadingState label="Loading your applications…" />
          ) : apps.length ? (
            <div className="app-list">
              {apps.map((app) => {
                const score = app.match_details?.score ?? app.compatibility_score;
                const jobId = app.job_offer_id || app.match_details?.job_offer_id;
                const isPolling = pollingIds.has(app.id);

                return (
                  <div className="app-row" key={app.id}>
                    <span
                      className={`status-dot ${
                        app.status === 'SENT' ? 'sent' : ''
                      } ${
                        app.status === 'FAILED' || app.status === 'REJECTED'
                          ? 'failed'
                          : ''
                      } ${
                        isPolling ? 'disc-spin' : ''
                      }`}
                      style={{
                        animation: isPolling ? 'pulse 1.5s ease-in-out infinite' : undefined
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                        <div style={{ flex: 1 }}>
                          <strong className="app-job-title">
                            {app.match_details?.job_title || 'Tracked Opportunity'}
                          </strong>
                          <div className="muted">
                            {app.match_details?.company || 'Company'} ·{' '}
                            {formatDate(app.submitted_at || app.created_at)}
                          </div>
                          <div style={{ marginTop: '6px' }}>
                            <StatusBadge status={app.status} />
                            <span style={{ fontSize: '11px', color: 'var(--muted)', marginLeft: '8px' }}>
                              {statusDescription[app.status] || app.status}
                            </span>
                          </div>
                          {app.failure_reason && (
                            <div className="notice" style={{ marginTop: 6 }}>
                              {app.failure_reason}
                            </div>
                          )}
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
                          <MatchScore score={score} />
                          <span style={{ fontSize: '11px', fontWeight: 600, color: app.mode === 'FULL_AUTO' ? '#15803d' : 'var(--muted)' }}>
                            {app.mode === 'FULL_AUTO' ? '🤖 Auto' : app.mode === 'ASSISTED' ? '👤 Assisted' : '👤 Manual'}
                          </span>
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {canApprove(app) && (
                          <button
                            onClick={() => handleApprove(app.id)}
                            disabled={loadingId === app.id}
                            className="button primary"
                            style={{ fontSize: '12px', padding: '6px 12px' }}
                          >
                            {loadingId === app.id ? (
                              <><RefreshCw size={12} className="disc-spin" /> Approving...</>
                            ) : (
                              <><CheckCircle2 size={12} /> Approve</>
                            )}
                          </button>
                        )}
                        
                        {canReject(app) && (
                          <button
                            onClick={() => handleReject(app.id)}
                            disabled={loadingId === app.id}
                            className="button secondary"
                            style={{ fontSize: '12px', padding: '6px 12px' }}
                          >
                            {loadingId === app.id ? (
                              <><RefreshCw size={12} className="disc-spin" /> Rejecting...</>
                            ) : (
                              <><X size={12} /> Reject</>
                            )}
                          </button>
                        )}

                        <button
                          onClick={() => setSelectedApp(app)}
                          className="button secondary"
                          style={{ fontSize: '12px', padding: '6px 12px' }}
                        >
                          <Eye size={12} /> Details
                        </button>

                        {jobId && (
                          <Link
                            href={`/jobs/${jobId}`}
                            className="button secondary"
                            style={{ fontSize: '12px', padding: '6px 12px' }}
                          >
                            <ExternalLink size={12} /> View Job
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No applications yet"
              message="When you choose to track an opportunity from Discover or Job Detail, it will appear here."
            />
          )}
        </section>
      </div>

      {/* Detail Modal */}
      {selectedApp && (
        <ApplicationDetailModal
          application={selectedApp}
          onClose={() => setSelectedApp(null)}
          onUpdate={(updated) => {
            setApps(prev => prev.map(app => app.id === updated.id ? updated : app));
            setSelectedApp(updated);
          }}
        />
      )}
    </CandidateShell>
  );
}
