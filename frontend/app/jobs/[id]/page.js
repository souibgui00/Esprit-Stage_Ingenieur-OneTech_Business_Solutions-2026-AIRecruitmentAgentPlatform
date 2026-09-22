'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import CandidateShell from '../../../components/layout/CandidateShell';
import { jobsApi } from '../../../lib/api/jobs';
import { cvApi } from '../../../lib/api/cv';
import { matchingApi } from '../../../lib/api/matching';
import { getMatchLabel } from '../../../components/ui';
import {
  ArrowLeft, Briefcase, MapPin, Sparkles, CheckCircle2, AlertCircle,
  FileText, ExternalLink, RefreshCw, Zap, ShieldCheck, Clock, Target
} from 'lucide-react';

/* ── Factor weights ─────────────────────────────────────────── */
const FACTORS = [
  { key: 'skills_score',        label: 'Skills Alignment',      max: 35, desc: 'Essential & nice-to-have skill match' },
  { key: 'experience_score',    label: 'Experience Relevance',  max: 20, desc: 'Relevant work history' },
  { key: 'semantic_score',      label: 'Semantic Fit',          max: 15, desc: 'Contextual embedding similarity' },
  { key: 'seniority_score',     label: 'Seniority Alignment',   max: 10, desc: 'Career stage fit' },
  { key: 'llm_score',           label: 'AI Evaluation',         max: 10, desc: 'Qualitative LLM assessment' },
  { key: 'certification_bonus', label: 'Certifications',        max: 5,  desc: 'Relevant certification bonus' },
];

function scoreColor(score) {
  if (score >= 85) return 'var(--pine)';
  if (score >= 75) return '#16a34a';
  if (score >= 60) return '#ca8a04';
  return '#dc2626';
}

/* ── Animated score ring ────────────────────────────────────── */
function ScoreRing({ score }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = scoreColor(score);
  const label = getMatchLabel(score);

  return (
    <div className="detail-score-ring-wrap" style={{ width: 140, height: 140 }}>
      <svg className="detail-score-svg" viewBox="0 0 130 130" style={{ position: 'absolute', inset: 0 }}>
        <circle cx={65} cy={65} r={r} fill="none" stroke="var(--line)" strokeWidth={9} />
        <circle
          cx={65} cy={65} r={r} fill="none"
          stroke={color} strokeWidth={9}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeDashoffset={circ / 4}
          style={{ transition: 'stroke-dasharray 0.9s cubic-bezier(.16,1,.3,1)' }}
        />
      </svg>
      <div className="detail-score-content">
        <span className="detail-score-number" style={{ color }}>{Math.round(score)}</span>
        <span className="detail-score-tag">%</span>
        <span className="detail-score-tag" style={{ fontSize: 10, marginTop: 2 }}>{label}</span>
      </div>
    </div>
  );
}

/* ── Factor progress bar ────────────────────────────────────── */
function FactorBar({ factor, value }) {
  const pct = Math.min(100, Math.max(0, (value / factor.max) * 100));
  return (
    <div className="detail-factor-item">
      <div className="detail-factor-head">
        <span className="detail-factor-name">{factor.label}</span>
        <span className="detail-factor-val">
          <strong>{Number(value ?? 0).toFixed(1)}</strong> / {factor.max}
        </span>
      </div>
      <div className="detail-factor-bar">
        <div className="detail-factor-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="detail-factor-desc">{factor.desc}</span>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   MAIN PAGE
════════════════════════════════════════════════════════════ */
export default function JobDetail() {
  const { id } = useParams();
  const router = useRouter();

  const [job, setJob]       = useState(null);
  const [cv, setCv]         = useState(null);
  const [cvLoaded, setCvLoaded] = useState(false);
  const [match, setMatch]   = useState(null);           // null = not found yet
  const [matchState, setMatchState] = useState('loading'); // 'loading'|'found'|'pending'|'no-cv'
  const [error, setError]   = useState('');
  const [recomputing, setRecomputing] = useState(false);
  const [trackMsg, setTrackMsg] = useState('');

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        // Load job and CV in parallel
        const [offer, cvs] = await Promise.all([
          jobsApi.getOffer(id),
          cvApi.list(),
        ]);
        if (!alive) return;

        setJob(offer);
        setCvLoaded(true);

        if (!cvs || cvs.length === 0) {
          setMatchState('no-cv');
          return;
        }

        const activeCv = cvs[0];
        setCv(activeCv);

        if (activeCv.status !== 'PARSED') {
          setMatchState('pending');
          return;
        }

        // Try to get precomputed match
        try {
          const m = await matchingApi.getExplanation(activeCv.id, id);
          if (alive) { setMatch(m); setMatchState('found'); }
        } catch (e) {
          if (e.response?.status === 404) {
            // Match not yet computed — mark as pending (agent will evaluate)
            if (alive) setMatchState('pending');
          } else {
            if (alive) setError('Could not retrieve match analysis.');
          }
        }
      } catch (e) {
        if (alive) setError('Could not load this opportunity.');
      }
    }

    load();
    return () => { alive = false; };
  }, [id]);

  /* Recompute (admin/debug action — not primary UX) */
  const handleRecompute = useCallback(async () => {
    if (!cv || !job) return;
    setRecomputing(true);
    try {
      const m = await matchingApi.computeMatch(cv.id, job.id);
      setMatch(m);
      setMatchState('found');
    } catch (e) {
      setError(e.response?.data?.detail || 'Evaluation failed.');
    } finally {
      setRecomputing(false);
    }
  }, [cv, job]);

  /* ── Render guards ── */
  if (error && !job) return (
    <CandidateShell>
      <div className="page">
        <div className="disc-error"><AlertCircle size={16} /> {error}</div>
      </div>
    </CandidateShell>
  );
  if (!job) return (
    <CandidateShell>
      <div className="page">
        <div className="disc-skeleton-feed"><div className="disc-phase-spinner" /></div>
      </div>
    </CandidateShell>
  );

  const sidebarMatchLabel = match ? getMatchLabel(match.compatibility_score) : null;

  return (
    <CandidateShell>
      <div className="page detail-page">

        {/* Back */}
        <div className="detail-nav">
          <Link className="disc-quiet-link" href="/jobs">
            <ArrowLeft size={15} /> Back to opportunities
          </Link>
        </div>

        {/* Hero */}
        <div className="detail-hero disc-enter">
          <div className="detail-hero-main">
            <p className="eyebrow"><Sparkles size={11} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />Opportunity</p>
            <h1 className="detail-title">{job.title}</h1>
            <p className="detail-company">
              <strong>{job.company}</strong>
              {job.location && <> · <MapPin size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> {job.location}</>}
              {job.contract_type && <> · <Briefcase size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> {job.contract_type}</>}
            </p>
          </div>
          <div className="detail-hero-actions">
            {job.source_url && (
              <a className="button secondary" href={job.source_url} target="_blank" rel="noreferrer">
                <ExternalLink size={14} /> Original Posting
              </a>
            )}
          </div>
        </div>

        {trackMsg && (
          <div className="disc-agent-bar disc-enter">
            <CheckCircle2 size={14} /> {trackMsg}
          </div>
        )}
        {error && (
          <div className="disc-error disc-enter">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* Main Grid */}
        <div className="detail-grid disc-enter disc-enter--1">
          <div className="detail-left">

            {/* ── AI Match Analysis ── */}
            <section className="card detail-card">
              <div className="detail-card-header">
                <h2 className="section-title"><Sparkles size={16} className="icon-pine" /> AI Match Analysis</h2>
                {match && (
                  <button className="disc-quiet-link" onClick={handleRecompute} disabled={recomputing} title="Recalculate">
                    <RefreshCw size={12} className={recomputing ? 'disc-spin' : ''} />
                    {recomputing ? 'Recalculating…' : 'Recalculate'}
                  </button>
                )}
              </div>

              {/* STATE: No CV */}
              {matchState === 'no-cv' && (
                <div className="detail-state-box state-warning">
                  <FileText size={26} className="state-icon" />
                  <div>
                    <h3>Upload your CV to unlock compatibility analysis</h3>
                    <p>Our AI agent will automatically evaluate this opportunity against your profile.</p>
                    <Link href="/cv" className="button primary" style={{ marginTop: 12, display: 'inline-flex' }}>Upload CV</Link>
                  </div>
                </div>
              )}

              {/* STATE: CV processing / match pending */}
              {matchState === 'pending' && (
                <div className="detail-state-box state-info">
                  <Zap size={26} className="state-icon" />
                  <div>
                    <h3>No compatibility score yet</h3>
                    <p>
                      {cv?.status !== 'PARSED'
                        ? 'Your CV profile is still being prepared. Compatibility will be calculated automatically once ready.'
                        : "This opportunity hasn't been evaluated yet. The AI agent will analyze it when ranking your next recommendations."
                      }
                    </p>
                    {cv?.status === 'PARSED' && (
                      <button
                        className="button primary"
                        style={{ marginTop: 12 }}
                        onClick={handleRecompute}
                        disabled={recomputing}
                      >
                        {recomputing
                          ? <><RefreshCw size={14} className="disc-spin" /> Evaluating…</>
                          : <><Sparkles size={14} /> Evaluate Now</>
                        }
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* STATE: Loading */}
              {matchState === 'loading' && (
                <div className="disc-ai-status" style={{ padding: '24px 0' }}>
                  <div className="disc-phase-spinner" />
                  <span>Retrieving AI analysis…</span>
                </div>
              )}

              {/* STATE: Match found — show full breakdown */}
              {matchState === 'found' && match && (
                <div className="detail-match-body">
                  {match.summary && (
                    <div className="detail-summary-box">
                      <p className="detail-summary-text">"{match.summary}"</p>
                    </div>
                  )}

                  <div className="detail-factors-section">
                    <h4 className="detail-sub-title">6-Factor Breakdown</h4>
                    <div className="detail-factors-list">
                      {FACTORS.map(f => (
                        <FactorBar key={f.key} factor={f} value={match[f.key] ?? 0} />
                      ))}
                    </div>
                  </div>

                  <div className="detail-points-grid">
                    <div className="detail-points-box">
                      <h4 className="detail-points-head positive">
                        <CheckCircle2 size={15} /> Strengths & Matched Skills
                      </h4>
                      {match.matching_points?.length > 0
                        ? <ul className="detail-points-list">{match.matching_points.map((p, i) => <li key={i}><span className="chip match">{p}</span></li>)}</ul>
                        : <p className="disc-empty-sub">No specific strengths returned.</p>
                      }
                    </div>
                    <div className="detail-points-box">
                      <h4 className="detail-points-head gap">
                        <AlertCircle size={15} /> Gaps & Areas to Develop
                      </h4>
                      {match.gap_points?.length > 0
                        ? <ul className="detail-points-list">{match.gap_points.map((p, i) => <li key={i}><span className="chip">{p}</span></li>)}</ul>
                        : <p className="disc-empty-sub">No major gaps identified.</p>
                      }
                    </div>
                  </div>
                </div>
              )}
            </section>

            {/* Job description */}
            <section className="card detail-card" style={{ marginTop: 20 }}>
              <h2 className="section-title">About This Opportunity</h2>
              <div className="detail-description">{job.description}</div>
            </section>
          </div>

          {/* Sidebar */}
          <div className="detail-right">
            <div className="card detail-sidebar-card">
              <h3 className="detail-sidebar-title">Compatibility</h3>
              {match ? (
                <div className="detail-gauge-container">
                  <ScoreRing score={match.compatibility_score} />
                  <p className="detail-gauge-sub">Evaluated by the 6-factor AI matching engine.</p>
                </div>
              ) : (
                <div className="detail-gauge-container">
                  <div style={{ width: 140, height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Clock size={36} style={{ color: 'var(--muted)' }} />
                  </div>
                  <p className="detail-gauge-sub">
                    {matchState === 'no-cv' ? 'Upload CV to calculate.' :
                     matchState === 'pending' ? 'Analysis pending.' :
                     'Loading analysis…'}
                  </p>
                </div>
              )}
            </div>

            <div className="card detail-sidebar-card" style={{ marginTop: 14 }}>
              <h3 className="detail-sidebar-title">Application Decision</h3>
              <EligibilityWidget jobId={job.id} match={match} />
            </div>

            <div className="card detail-sidebar-card" style={{ marginTop: 14 }}>
              <h3 className="detail-sidebar-title">Role Details</h3>
              <div className="detail-meta-list">
                <div className="detail-meta-item">
                  <Briefcase size={14} />
                  <div>
                    <span className="detail-meta-label">Contract</span>
                    <span className="detail-meta-val">{job.contract_type || 'Not specified'}</span>
                  </div>
                </div>
                <div className="detail-meta-item">
                  <MapPin size={14} />
                  <div>
                    <span className="detail-meta-label">Location</span>
                    <span className="detail-meta-val">{job.location || 'Not specified'}</span>
                  </div>
                </div>
                <div className="detail-meta-item">
                  <ShieldCheck size={14} />
                  <div>
                    <span className="detail-meta-label">Source</span>
                    <span className="detail-meta-val" style={{ textTransform: 'capitalize' }}>
                      {job.source_name || 'Platform'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </CandidateShell>
  );
}

function EligibilityWidget({ jobId, match }) {
  const [eligibility, setEligibility] = useState(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [appliedApp, setAppliedApp] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadEligibility() {
      try {
        const { applicationsApi } = await import('../../../lib/api/applications');
        const res = await applicationsApi.checkEligibility(jobId);
        setEligibility(res);
      } catch (err) {
        console.error('Eligibility check failed:', err);
      } finally {
        setLoading(false);
      }
    }
    loadEligibility();
  }, [jobId]);

  const handleApply = async () => {
    if (!match?.id) return;
    setApplying(true);
    setError('');
    try {
      const { applicationsApi } = await import('../../../lib/api/applications');
      const app = await applicationsApi.createFromMatch(match.id);
      setAppliedApp(app);
      setEligibility(prev => prev ? { ...prev, already_applied: true } : prev);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit application.');
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return <div style={{ fontSize: '13px', color: 'var(--muted)' }}>Evaluating agent rules…</div>;
  }

  if (!eligibility) {
    return null;
  }

  if (appliedApp || eligibility.already_applied) {
    return (
      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '14px', fontSize: '13px', color: '#166534' }}>
        <div style={{ fontWeight: 700, marginBottom: '4px' }}>✓ Application Submitted</div>
        <p style={{ margin: 0, fontSize: '12px', color: '#15803d' }}>
          You have already applied to this opportunity. Track status in Applications.
        </p>
        <Link href="/applications" className="button secondary" style={{ marginTop: '10px', fontSize: '12px', padding: '4px 10px' }}>
          View Applications
        </Link>
      </div>
    );
  }

  const checks = eligibility.checks || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {eligibility.application_mode === 'RECOMMEND_ONLY' ? (
        <div style={{ background: 'var(--mint)', border: '1px solid var(--pine-light)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontWeight: 800, fontSize: '14px', color: 'var(--pine-dark)', marginBottom: '4px' }}>
            👤 AI Recommended
          </div>
          <p style={{ fontSize: '12px', color: 'var(--ink)', margin: 0, lineHeight: 1.5 }}>
            Your AI agent recommends this opportunity based on your profile, CV, and preferences. You decide whether to apply.
          </p>
        </div>
      ) : eligibility.application_mode === 'ASSISTED' ? (
        <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontWeight: 800, fontSize: '14px', color: '#1e40af', marginBottom: '4px' }}>
            🤝 Assisted Mode
          </div>
          <p style={{ fontSize: '12px', color: '#1e3a8a', margin: 0, lineHeight: 1.5 }}>
            Your AI agent will create an application for your review. You can review and approve before submission.
          </p>
        </div>
      ) : eligibility.eligible ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontWeight: 800, fontSize: '14px', color: '#166534', marginBottom: '4px' }}>
            🤖 Eligible for Automatic Application
          </div>
          <p style={{ fontSize: '12px', color: '#15803d', margin: '0 0 10px', lineHeight: 1.4 }}>
            Your AI agent can apply to this opportunity because it satisfies your configured preferences.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11.5px', color: '#166534', marginBottom: '10px' }}>
            {checks.score_check && <div>✓ Score: {Math.round(checks.score_check.actual)}% ≥ {checks.score_check.required}%</div>}
            {checks.preference_check?.passed && <div>✓ Location & Contract match</div>}
            {checks.daily_limit_check?.passed && <div>✓ Daily limit available ({checks.daily_limit_check.used_today}/{checks.daily_limit_check.max_per_day})</div>}
          </div>
        </div>
      ) : (
        <div style={{ background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontWeight: 800, fontSize: '13.5px', color: '#9f1239', marginBottom: '4px' }}>
            Not Eligible for Auto-Apply
          </div>
          <p style={{ fontSize: '12px', color: '#be123c', margin: 0, lineHeight: 1.4 }}>
            Reason: {eligibility.reasons?.[0] || eligibility.summary_reason}
          </p>
        </div>
      )}

      {error && <div style={{ color: '#dc2626', fontSize: '12px' }}>{error}</div>}

      <button
        onClick={handleApply}
        disabled={applying || !match}
        className="button primary"
        style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontWeight: 700 }}
      >
        {applying ? 'Submitting Application…' : 'Apply Now'}
      </button>
    </div>
  );
}
