'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import CandidateShell from '../../components/layout/CandidateShell';
import { applicationsApi } from '../../lib/api/applications';
import { Sparkles, Clock, CheckCircle2, AlertTriangle, ShieldCheck, Zap } from 'lucide-react';

export default function AgentActivityPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [triggering, setTriggering] = useState(false);

  async function loadLogs() {
    try {
      setLoading(true);
      const res = await applicationsApi.getActivity(30);
      setLogs(res || []);
    } catch (err) {
      console.error(err);
      setError('Could not load agent activity logs.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLogs();
  }, []);

  const handleRunNow = async () => {
    setTriggering(true);
    try {
      await applicationsApi.runAutoApplyCycle();
      await loadLogs();
    } catch (err) {
      console.error(err);
    } finally {
      setTriggering(false);
    }
  };

  const getActionIcon = (action) => {
    switch (action) {
      case 'AUTO_APPLIED':
        return <CheckCircle2 size={16} style={{ color: '#166534' }} />;
      case 'SKIPPED_OPPORTUNITY':
      case 'SKIPPED_LIMIT':
        return <AlertTriangle size={16} style={{ color: '#ca8a04' }} />;
      case 'EVALUATED_MATCHES':
        return <Zap size={16} style={{ color: 'var(--pine)' }} />;
      default:
        return <Clock size={16} style={{ color: 'var(--muted)' }} />;
    }
  };

  return (
    <CandidateShell>
      <div className="page disc-page">
        <div className="disc-header disc-enter" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <p className="eyebrow"><Sparkles size={12} style={{ display: 'inline', marginRight: 4 }} /> Transparency & Trust</p>
            <h1 className="disc-title">🤖 Agent Activity Log</h1>
            <p className="disc-subtitle">
              Complete chronological audit of actions, evaluations, and applications executed by your AI Recruitment Agent.
            </p>
          </div>
          <button onClick={handleRunNow} disabled={triggering} className="button primary" style={{ marginTop: '8px' }}>
            {triggering ? 'Agent Running...' : '⚡ Trigger Agent Run'}
          </button>
        </div>

        <section className="section card disc-enter disc-enter--1" style={{ marginTop: '20px' }}>
          {error ? (
            <div className="disc-error">{error}</div>
          ) : loading ? (
            <div className="disc-skeleton-feed"><div className="disc-phase-spinner" /> Loading agent activity...</div>
          ) : logs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <Clock size={40} style={{ color: 'var(--muted)', marginBottom: '12px' }} />
              <h3>No agent activity recorded yet</h3>
              <p style={{ color: 'var(--muted)', fontSize: '14px', maxWidth: '400px', margin: '8px auto 16px' }}>
                Your AI agent logs evaluations, decision checks, and applications here for complete transparency.
              </p>
              <button onClick={handleRunNow} disabled={triggering} className="button primary">
                Run Agent Evaluation Cycle
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {logs.map((log) => (
                <div
                  key={log.id}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '14px',
                    padding: '14px 16px',
                    borderRadius: '10px',
                    background: log.action === 'AUTO_APPLIED' ? '#f0fdf4' : 'var(--paper)',
                    border: `1px solid ${log.action === 'AUTO_APPLIED' ? '#bbf7d0' : 'var(--line)'}`
                  }}
                >
                  <div style={{ marginTop: '2px' }}>{getActionIcon(log.action)}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 700, fontSize: '13.5px', color: 'var(--ink)' }}>
                        {log.action.replace(/_/g, ' ')}
                      </span>
                      <span style={{ fontSize: '11.5px', color: 'var(--muted)' }}>
                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {new Date(log.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: '13px', color: 'var(--ink-light)', lineHeight: 1.4 }}>
                      {log.message}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </CandidateShell>
  );
}
