'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { authApi } from '../../lib/api/auth';
import { applicationsApi } from '../../lib/api/applications';
import { useAuth } from '../../context/AuthContext';
import CandidateShell from '../../components/layout/CandidateShell';
import {
  Settings, Bot, Target, Zap, Save, User,
  CheckCircle2, AlertCircle, Sliders, MapPin,
  Briefcase, DollarSign, Shield
} from 'lucide-react';

const CONTRACT_OPTIONS = [
  { id: 'STAGE', label: 'Stage / Internship', emoji: '🎓' },
  { id: 'CDI', label: 'CDI / Permanent', emoji: '📋' },
  { id: 'CDD', label: 'CDD / Fixed-Term', emoji: '📅' },
  { id: 'FREELANCE', label: 'Freelance', emoji: '💼' },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningAgent, setRunningAgent] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [agentRunResult, setAgentRunResult] = useState(null);

  const [keywords, setKeywords] = useState('');
  const [locations, setLocations] = useState('');
  const [contractTypes, setContractTypes] = useState([]);
  const [remotePref, setRemotePref] = useState(false);
  const [minSalary, setMinSalary] = useState('');
  const [targetRoles, setTargetRoles] = useState('');
  const [appMode, setAppMode] = useState('RECOMMEND_ONLY');
  const [minMatchScore, setMinMatchScore] = useState(80);
  const [maxAppsPerDay, setMaxAppsPerDay] = useState(5);

  useEffect(() => {
    async function fetchPrefs() {
      setLoading(true);
      try {
        const data = await authApi.getPreferences();
        if (data) {
          setKeywords(data.job_keywords || '');
          setLocations(Array.isArray(data.preferred_locations) ? data.preferred_locations.join(', ') : '');
          setContractTypes(Array.isArray(data.preferred_contract_types) ? data.preferred_contract_types : []);
          setRemotePref(!!data.remote_preference);
          setMinSalary(data.min_salary != null ? data.min_salary : '');
          setTargetRoles(Array.isArray(data.target_roles) ? data.target_roles.join(', ') : '');
          setAppMode(data.application_mode || 'RECOMMEND_ONLY');
          setMinMatchScore(data.min_match_score != null ? data.min_match_score : 80);
          setMaxAppsPerDay(data.max_applications_per_day != null ? data.max_applications_per_day : 5);
        }
      } catch (err) {
        setError('Could not load your settings. Please refresh the page.');
      } finally {
        setLoading(false);
      }
    }
    fetchPrefs();
  }, []);

  const handleContractToggle = (type) => {
    setContractTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const locList = locations.split(',').map(s => s.trim()).filter(Boolean);
      const roleList = targetRoles.split(',').map(s => s.trim()).filter(Boolean);
      await authApi.updatePreferences({
        job_keywords: keywords,
        preferred_locations: locList,
        preferred_contract_types: contractTypes,
        remote_preference: remotePref,
        min_salary: minSalary ? parseInt(minSalary, 10) : null,
        target_roles: roleList,
        application_mode: appMode,
        min_match_score: parseFloat(minMatchScore),
        max_applications_per_day: parseInt(maxAppsPerDay, 10),
      });
      setMessage('Settings saved successfully!');
      setTimeout(() => setMessage(''), 4000);
    } catch (err) {
      setError('Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerAgent = async () => {
    setRunningAgent(true);
    setAgentRunResult(null);
    try {
      const res = await applicationsApi.runAutoApplyCycle();
      setAgentRunResult(res);
    } catch (err) {
      console.error('Agent run failed:', err);
    } finally {
      setRunningAgent(false);
    }
  };

  return (
    <CandidateShell>
      <div className="page" style={{ maxWidth: '820px' }}>

        {/* Header */}
        <div style={{ marginBottom: '36px' }}>
          <p className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <Settings size={12} /> Job Preferences & Agent Autonomy
          </p>
          <h1 style={{ fontSize: 'clamp(28px, 4vw, 40px)', fontWeight: 800, letterSpacing: '-0.04em', margin: '0 0 10px', color: 'var(--ink)' }}>
            Settings
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: '15px', margin: 0 }}>
            Configure what opportunities you want and how much autonomy your AI recruitment agent has.
          </p>
        </div>

        {/* Success banner */}
        {message && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            background: '#f0fdf4', border: '1px solid #bbf7d0',
            borderRadius: '12px', padding: '14px 18px',
            color: '#166534', fontWeight: 600, fontSize: '14px', marginBottom: '24px'
          }}>
            <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
            {message}
          </div>
        )}
        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            background: '#fff1f2', border: '1px solid #fecdd3',
            borderRadius: '12px', padding: '14px 18px',
            color: '#9f1239', fontWeight: 600, fontSize: '14px', marginBottom: '24px'
          }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {[1, 2].map(i => (
              <div key={i} className="card" style={{
                height: '180px', background: 'linear-gradient(90deg, var(--soft) 25%, #eef1ee 50%, var(--soft) 75%)',
                backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite'
              }} />
            ))}
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

            {/* ── SECTION 1: AI AGENT AUTONOMY ── */}
            <div className="card" style={{ padding: '28px', background: 'linear-gradient(135deg, #f8fdf9 0%, #ffffff 100%)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                    <div style={{ background: 'var(--mint)', borderRadius: '10px', padding: '8px', display: 'flex' }}>
                      <Bot size={18} style={{ color: 'var(--pine)' }} />
                    </div>
                    <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>AI Agent Autonomy</h2>
                  </div>
                  <p style={{ fontSize: '13.5px', color: 'var(--muted)', margin: 0, maxWidth: '480px' }}>
                    Controls whether the AI agent recommends opportunities or applies automatically on your behalf.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleTriggerAgent}
                  disabled={runningAgent}
                  className="button secondary"
                  style={{ fontSize: '13px', whiteSpace: 'nowrap' }}
                >
                  <Zap size={14} />
                  {runningAgent ? 'Agent Running…' : 'Trigger Agent Run'}
                </button>
              </div>

              {agentRunResult && (
                <div style={{
                  background: 'var(--mint)', border: '1px solid #b6dcc2', borderRadius: '10px',
                  padding: '14px 18px', marginBottom: '20px', fontSize: '13.5px', color: 'var(--pine-dark)'
                }}>
                  <strong>Agent run complete:</strong> Evaluated {agentRunResult.evaluated_count} jobs,
                  applied to {agentRunResult.applied_count}, skipped {agentRunResult.skipped_count}.{' '}
                  Mode: <strong>{agentRunResult.mode}</strong>
                </div>
              )}

              {/* Mode selector */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px', marginBottom: '24px' }}>
                {[
                  {
                    mode: 'RECOMMEND_ONLY',
                    icon: '👤',
                    title: 'Recommend Only',
                    badge: 'Default',
                    badgeColor: 'var(--muted)',
                    desc: 'The agent ranks and recommends opportunities. You decide when to submit each application.'
                  },
                  {
                    mode: 'ASSISTED',
                    icon: '🤝',
                    title: 'Assisted',
                    badge: 'New',
                    badgeColor: 'var(--pine)',
                    desc: 'The agent generates applications for review. You approve before submission.'
                  },
                  {
                    mode: 'AUTO_APPLY',
                    icon: '🤖',
                    title: 'Auto Apply',
                    badge: 'Automatic',
                    badgeColor: 'var(--pine)',
                    desc: 'The agent automatically submits applications that satisfy all your rules.'
                  }
                ].map(({ mode, icon, title, badge, badgeColor, desc }) => {
                  const active = appMode === mode;
                  return (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setAppMode(mode)}
                      style={{
                        border: `2px solid ${active ? 'var(--pine)' : 'var(--line)'}`,
                        background: active ? 'var(--mint)' : '#fff',
                        borderRadius: '14px',
                        padding: '16px',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.18s ease',
                        transform: active ? 'scale(1.01)' : 'scale(1)',
                        boxShadow: active ? '0 4px 16px rgba(21, 91, 61, 0.12)' : 'none',
                      }}
                    >
                      <div style={{ fontSize: '20px', marginBottom: '6px' }}>{icon}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <span style={{ fontWeight: 800, fontSize: '14px', color: 'var(--ink)' }}>{title}</span>
                        <span style={{
                          fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
                          background: active ? 'var(--pine)' : 'var(--soft)',
                          color: active ? '#fff' : 'var(--muted)',
                          padding: '2px 6px', borderRadius: '999px'
                        }}>{badge}</span>
                      </div>
                      <p style={{ fontSize: '11.5px', color: 'var(--muted)', margin: 0, lineHeight: 1.4 }}>{desc}</p>
                    </button>
                  );
                })}
              </div>

              {/* Rules */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '8px' }}>
                    <Sliders size={13} style={{ display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                    Minimum Match Score for Auto-Apply (%)
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type="number" min="50" max="100"
                      value={minMatchScore}
                      onChange={e => setMinMatchScore(e.target.value)}
                      style={{
                        width: '100%', padding: '10px 14px', border: '1.5px solid var(--line)',
                        borderRadius: '10px', fontSize: '15px', fontWeight: 700,
                        background: '#fff', color: 'var(--ink)', outline: 'none',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '6px 0 0' }}>
                    Jobs below this threshold won't be auto-applied.
                  </p>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '8px' }}>
                    <Shield size={13} style={{ display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                    Maximum Applications Per Day
                  </label>
                  <input
                    type="number" min="1" max="50"
                    value={maxAppsPerDay}
                    onChange={e => setMaxAppsPerDay(e.target.value)}
                    style={{
                      width: '100%', padding: '10px 14px', border: '1.5px solid var(--line)',
                      borderRadius: '10px', fontSize: '15px', fontWeight: 700,
                      background: '#fff', color: 'var(--ink)', outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                  <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '6px 0 0' }}>
                    Prevents spam and respects platform rate limits.
                  </p>
                </div>
              </div>
            </div>

            {/* ── SECTION 2: JOB SEARCH CRITERIA ── */}
            <div className="card" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px' }}>
                <div style={{ background: '#fff7ed', borderRadius: '10px', padding: '8px', display: 'flex' }}>
                  <Target size={18} style={{ color: '#b97820' }} />
                </div>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Job Search Criteria</h2>
                  <p style={{ fontSize: '13px', color: 'var(--muted)', margin: '2px 0 0' }}>
                    What types of opportunities are you looking for?
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Target Roles */}
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '8px' }}>
                    <Briefcase size={13} style={{ display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                    Target Roles
                  </label>
                  <input
                    type="text"
                    value={targetRoles}
                    onChange={e => setTargetRoles(e.target.value)}
                    placeholder="e.g. Software Engineer, Fullstack Developer, AI Engineer"
                    style={inputStyle}
                  />
                  <p style={hintStyle}>Comma-separated role keywords. Used for matching and auto-apply eligibility.</p>
                </div>

                {/* Keywords */}
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '8px' }}>
                    Search Keywords & Technologies
                  </label>
                  <input
                    type="text"
                    value={keywords}
                    onChange={e => setKeywords(e.target.value)}
                    placeholder="e.g. Python, React, FastAPI, Docker, PostgreSQL"
                    style={inputStyle}
                  />
                </div>

                {/* Locations */}
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '8px' }}>
                    <MapPin size={13} style={{ display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                    Preferred Locations / Countries
                  </label>
                  <input
                    type="text"
                    value={locations}
                    onChange={e => setLocations(e.target.value)}
                    placeholder="e.g. France, Germany, Paris, Remote"
                    style={inputStyle}
                  />
                  <p style={hintStyle}>Comma-separated. Used to filter auto-apply eligibility.</p>
                </div>

                {/* Contract types */}
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '10px' }}>
                    Preferred Contract Types
                  </label>
                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    {CONTRACT_OPTIONS.map(c => {
                      const active = contractTypes.includes(c.id);
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => handleContractToggle(c.id)}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: '7px',
                            padding: '8px 16px', borderRadius: '999px', cursor: 'pointer',
                            fontSize: '13px', fontWeight: 600, transition: 'all 0.15s ease',
                            border: `1.5px solid ${active ? 'var(--pine)' : 'var(--line)'}`,
                            background: active ? 'var(--mint)' : '#fff',
                            color: active ? 'var(--pine-dark)' : 'var(--ink)',
                          }}
                        >
                          <span>{c.emoji}</span>
                          {c.label}
                          {active && <CheckCircle2 size={13} style={{ color: 'var(--pine)' }} />}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Remote + Salary in a row */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', alignItems: 'start' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '10px' }}>
                      Remote Preference
                    </label>
                    <label style={{
                      display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer',
                      background: remotePref ? 'var(--mint)' : 'var(--soft)',
                      border: `1.5px solid ${remotePref ? 'var(--pine)' : 'var(--line)'}`,
                      borderRadius: '10px', padding: '12px 16px', transition: 'all 0.15s ease'
                    }}>
                      <input
                        type="checkbox" checked={remotePref}
                        onChange={e => setRemotePref(e.target.checked)}
                        style={{ width: '16px', height: '16px', accentColor: 'var(--pine)' }}
                      />
                      <span style={{ fontSize: '14px', fontWeight: 600, color: remotePref ? 'var(--pine-dark)' : 'var(--ink)' }}>
                        🌐 Remote only
                      </span>
                    </label>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--ink)', marginBottom: '8px' }}>
                      <DollarSign size={13} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
                      Minimum Annual Salary (EUR)
                    </label>
                    <input
                      type="number"
                      value={minSalary}
                      onChange={e => setMinSalary(e.target.value)}
                      placeholder="e.g. 45000"
                      style={inputStyle}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <Link href="/profile" className="button secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
                <User size={14} /> View Profile
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="button primary"
                style={{ padding: '11px 28px', fontWeight: 700, fontSize: '15px' }}
              >
                <Save size={15} />
                {saving ? 'Saving…' : 'Save Settings'}
              </button>
            </div>

          </form>
        )}
      </div>

      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button { opacity: 1; }
        input:focus { border-color: var(--pine) !important; outline: none; box-shadow: 0 0 0 3px rgba(21,91,61,0.12); }
      `}</style>
    </CandidateShell>
  );
}

const inputStyle = {
  width: '100%', padding: '11px 14px',
  border: '1.5px solid var(--line)', borderRadius: '10px',
  fontSize: '14.5px', color: 'var(--ink)', background: '#fff',
  outline: 'none', boxSizing: 'border-box',
  transition: 'border-color 0.15s ease',
  fontFamily: 'inherit',
};

const hintStyle = {
  fontSize: '12px', color: 'var(--muted)', margin: '6px 0 0',
};
