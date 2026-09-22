'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import CandidateShell from '../../components/layout/CandidateShell';
import { useAuth } from '../../context/AuthContext';
import { cvApi } from '../../lib/api/cv';
import {
  User, Mail, Phone, MapPin, Linkedin, Github, Globe, Briefcase,
  GraduationCap, Award, Wrench, FileText, Settings, ArrowRight,
  CheckCircle2, Sparkles, Edit3, Save, X
} from 'lucide-react';

export default function ProfilePage() {
  const { user } = useAuth();
  const [cvs, setCvs] = useState(null);
  const [cvDetail, setCvDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editingPersonal, setEditingPersonal] = useState(false);
  const [savingPersonal, setSavingPersonal] = useState(false);
  const [personalForm, setPersonalForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    location: '',
    linkedin_url: '',
    github_url: '',
  });

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const cvList = await cvApi.list();
        setCvs(cvList || []);

        if (cvList && cvList.length > 0) {
          const activeCv = cvList[0];
          if (activeCv.status === 'PARSED') {
            const detail = await cvApi.get(activeCv.id);
            setCvDetail(detail);

            if (detail.personal_info) {
              setPersonalForm({
                full_name: detail.personal_info.full_name || user?.full_name || '',
                email: detail.personal_info.email || user?.email || '',
                phone: detail.personal_info.phone || '',
                location: detail.personal_info.location || '',
                linkedin_url: detail.personal_info.linkedin_url || '',
                github_url: detail.personal_info.github_url || '',
              });
            }
          }
        }
      } catch (err) {
        console.error('Failed to load candidate profile:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [user]);

  const activeCv = cvs?.[0];
  const personal = cvDetail?.personal_info;

  const handleSavePersonalInfo = async (e) => {
    e.preventDefault();
    if (!activeCv) return;
    setSavingPersonal(true);
    try {
      await cvApi.updatePersonalInfo(activeCv.id, personalForm);
      const updatedDetail = await cvApi.get(activeCv.id);
      setCvDetail(updatedDetail);
      setEditingPersonal(false);
    } catch (err) {
      console.error('Failed to update personal info:', err);
    } finally {
      setSavingPersonal(false);
    }
  };

  const initials = (personalForm.full_name || user?.full_name || user?.email || 'Candidate')
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <CandidateShell>
      <div className="page" style={{ maxWidth: '880px' }}>

        {/* ── Page Header ── */}
        <div style={{ marginBottom: '32px' }}>
          <p className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <User size={12} /> Candidate Identity
          </p>
          <h1 style={{ fontSize: 'clamp(28px, 4vw, 40px)', fontWeight: 800, letterSpacing: '-0.04em', margin: '0 0 10px', color: 'var(--ink)' }}>
            Candidate Profile
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: '15px', margin: 0 }}>
            Your background, skills, education, and professional history. The AI agent uses this profile to evaluate your opportunity match.
          </p>
        </div>

        {/* Banner pointing to settings */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px',
          background: 'var(--mint)', border: '1px solid #b6dcc2', borderRadius: '12px',
          padding: '16px 20px', marginBottom: '24px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sparkles size={18} style={{ color: 'var(--pine)', flexShrink: 0 }} />
            <div style={{ fontSize: '13.5px', color: 'var(--pine-dark)' }}>
              Looking to adjust your <strong>target roles, location filters, or agent autonomy mode</strong>?
            </div>
          </div>
          <Link href="/settings" className="button primary" style={{ fontSize: '12.5px', padding: '7px 14px', whiteSpace: 'nowrap' }}>
            <Settings size={13} /> Open Settings
          </Link>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {[1, 2, 3].map(i => (
              <div key={i} className="card" style={{ height: '140px', background: 'var(--soft)', animation: 'shimmer 1.5s infinite' }} />
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

            {/* ── 1. PERSONAL INFORMATION & LINKS ── */}
            <div className="card" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{
                    width: '64px', height: '64px', borderRadius: '50%', flexShrink: 0,
                    background: 'linear-gradient(135deg, var(--pine) 0%, #1e7d52 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '22px', fontWeight: 800, color: '#fff'
                  }}>
                    {initials}
                  </div>
                  <div>
                    <h2 style={{ fontSize: '20px', fontWeight: 800, margin: '0 0 4px', color: 'var(--ink)' }}>
                      {personalForm.full_name || user?.full_name || 'Candidate Profile'}
                    </h2>
                    <p style={{ fontSize: '13.5px', color: 'var(--muted)', margin: 0 }}>
                      Personal Identity & Contact Information
                    </p>
                  </div>
                </div>

                {activeCv && activeCv.status === 'PARSED' && !editingPersonal && (
                  <button
                    onClick={() => setEditingPersonal(true)}
                    className="button secondary"
                    style={{ fontSize: '12.5px', padding: '6px 12px' }}
                  >
                    <Edit3 size={13} /> Edit Personal Info
                  </button>
                )}
              </div>

              {editingPersonal ? (
                <form onSubmit={handleSavePersonalInfo} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div>
                      <label style={labelStyle}>Full Name</label>
                      <input
                        type="text"
                        value={personalForm.full_name}
                        onChange={e => setPersonalForm({ ...personalForm, full_name: e.target.value })}
                        style={inputStyle}
                        placeholder="e.g. Jean Dupont"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Email</label>
                      <input
                        type="email"
                        value={personalForm.email}
                        onChange={e => setPersonalForm({ ...personalForm, email: e.target.value })}
                        style={inputStyle}
                        placeholder="e.g. jean@example.com"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Phone</label>
                      <input
                        type="text"
                        value={personalForm.phone}
                        onChange={e => setPersonalForm({ ...personalForm, phone: e.target.value })}
                        style={inputStyle}
                        placeholder="e.g. +33 6 12 34 56 78"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Location / City</label>
                      <input
                        type="text"
                        value={personalForm.location}
                        onChange={e => setPersonalForm({ ...personalForm, location: e.target.value })}
                        style={inputStyle}
                        placeholder="e.g. Paris, France"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>LinkedIn URL</label>
                      <input
                        type="url"
                        value={personalForm.linkedin_url}
                        onChange={e => setPersonalForm({ ...personalForm, linkedin_url: e.target.value })}
                        style={inputStyle}
                        placeholder="https://linkedin.com/in/..."
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>GitHub URL</label>
                      <input
                        type="url"
                        value={personalForm.github_url}
                        onChange={e => setPersonalForm({ ...personalForm, github_url: e.target.value })}
                        style={inputStyle}
                        placeholder="https://github.com/..."
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
                    <button type="button" onClick={() => setEditingPersonal(false)} className="button secondary" style={{ fontSize: '13px' }}>
                      <X size={13} /> Cancel
                    </button>
                    <button type="submit" disabled={savingPersonal} className="button primary" style={{ fontSize: '13px' }}>
                      <Save size={13} /> {savingPersonal ? 'Saving…' : 'Save Changes'}
                    </button>
                  </div>
                </form>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginTop: '12px' }}>
                  <div style={infoItemStyle}>
                    <Mail size={14} style={{ color: 'var(--muted)' }} />
                    <span style={{ fontSize: '13.5px', color: 'var(--ink)' }}>{personalForm.email || user?.email || 'Not specified'}</span>
                  </div>
                  <div style={infoItemStyle}>
                    <Phone size={14} style={{ color: 'var(--muted)' }} />
                    <span style={{ fontSize: '13.5px', color: 'var(--ink)' }}>{personalForm.phone || 'Not specified'}</span>
                  </div>
                  <div style={infoItemStyle}>
                    <MapPin size={14} style={{ color: 'var(--muted)' }} />
                    <span style={{ fontSize: '13.5px', color: 'var(--ink)' }}>{personalForm.location || 'Not specified'}</span>
                  </div>
                  <div style={infoItemStyle}>
                    <Linkedin size={14} style={{ color: '#0a66c2' }} />
                    {personalForm.linkedin_url ? (
                      <a href={personalForm.linkedin_url} target="_blank" rel="noreferrer" style={{ fontSize: '13.5px', color: 'var(--pine)', textDecoration: 'underline' }}>
                        LinkedIn Profile
                      </a>
                    ) : (
                      <span style={{ fontSize: '13.5px', color: 'var(--muted)' }}>No LinkedIn linked</span>
                    )}
                  </div>
                  <div style={infoItemStyle}>
                    <Github size={14} style={{ color: '#24292e' }} />
                    {personalForm.github_url ? (
                      <a href={personalForm.github_url} target="_blank" rel="noreferrer" style={{ fontSize: '13.5px', color: 'var(--pine)', textDecoration: 'underline' }}>
                        GitHub Profile
                      </a>
                    ) : (
                      <span style={{ fontSize: '13.5px', color: 'var(--muted)' }}>No GitHub linked</span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* ── 2. ACTIVE CV & DOCUMENT MANAGEMENT ── */}
            <div className="card" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ background: '#f0f9ff', borderRadius: '10px', padding: '8px', display: 'flex' }}>
                    <FileText size={18} style={{ color: '#0369a1' }} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>CV & Source Data</h3>
                    <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: '2px 0 0' }}>
                      The AI agent uses your uploaded CV to extract your skills and experience.
                    </p>
                  </div>
                </div>
                <Link href="/cv/upload" className="button primary" style={{ fontSize: '13px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <FileText size={13} /> {activeCv ? 'Replace CV' : 'Upload CV'}
                </Link>
              </div>

              {activeCv ? (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  background: '#f8fbf9', border: '1.5px solid var(--line)', borderRadius: '12px',
                  padding: '16px 20px'
                }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '14.5px', color: 'var(--ink)' }}>
                      {activeCv.filename || 'Active CV Document'}
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--pine)', fontWeight: 600, marginTop: '2px' }}>
                      ✓ Status: {activeCv.status} · Uploaded {new Date(activeCv.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <Link href={`/cv/${activeCv.id}`} className="button secondary" style={{ fontSize: '12.5px', padding: '6px 12px' }}>
                    Full CV View <ArrowRight size={13} />
                  </Link>
                </div>
              ) : (
                <div style={{ textAlignment: 'center', padding: '20px', background: 'var(--soft)', borderRadius: '12px', textAlign: 'center' }}>
                  <p style={{ fontSize: '14px', color: 'var(--muted)', margin: '0 0 12px' }}>No active CV uploaded yet.</p>
                  <Link href="/cv/upload" className="button primary" style={{ fontSize: '13px' }}>Upload CV Now</Link>
                </div>
              )}
            </div>

            {/* ── 3. SKILLS & TECHNICAL PROFILE ── */}
            <div className="card" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
                <div style={{ background: 'var(--mint)', borderRadius: '10px', padding: '8px', display: 'flex' }}>
                  <Wrench size={18} style={{ color: 'var(--pine)' }} />
                </div>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Skills & Technical Profile</h3>
                  <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: '2px 0 0' }}>
                    Extracted automatically by the AI parser from your CV.
                  </p>
                </div>
              </div>

              {cvDetail?.skills?.length ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {cvDetail.skills.map((skill, i) => (
                    <span key={i} style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      background: 'var(--soft)', border: '1px solid var(--line)',
                      borderRadius: '999px', padding: '6px 14px', fontSize: '13px',
                      fontWeight: 600, color: 'var(--ink)'
                    }}>
                      {skill.canonical_name || skill.name}
                      {skill.category && (
                        <span style={{ fontSize: '10px', color: 'var(--muted)', fontWeight: 500, textTransform: 'uppercase' }}>
                          · {skill.category}
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '13.5px', color: 'var(--muted)', margin: 0 }}>
                  {activeCv ? 'No skills extracted yet or parsing in progress.' : 'Upload a CV to automatically parse your technical skills.'}
                </p>
              )}
            </div>

            {/* ── 4. PROFESSIONAL EXPERIENCE ── */}
            <div className="card" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
                <div style={{ background: '#fef3c7', borderRadius: '10px', padding: '8px', display: 'flex' }}>
                  <Briefcase size={18} style={{ color: '#b45309' }} />
                </div>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Professional Experience</h3>
                  <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: '2px 0 0' }}>
                    Work history analyzed for experience relevance and seniority scoring.
                  </p>
                </div>
              </div>

              {cvDetail?.experiences?.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {cvDetail.experiences.map((exp, i) => (
                    <div key={i} style={{
                      borderLeft: '3px solid var(--pine)', paddingLeft: '16px',
                      paddingTop: '2px', paddingBottom: '2px'
                    }}>
                      <div style={{ fontWeight: 800, fontSize: '15px', color: 'var(--ink)' }}>{exp.title}</div>
                      <div style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--muted)', margin: '2px 0 4px' }}>
                        {exp.company} {exp.start_date && `· ${exp.start_date} - ${exp.is_current ? 'Present' : exp.end_date || ''}`}
                      </div>
                      {exp.description && (
                        <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0, lineHeight: 1.5 }}>
                          {exp.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '13.5px', color: 'var(--muted)', margin: 0 }}>
                  {activeCv ? 'No work experience parsed yet.' : 'Upload your CV to populate your professional history.'}
                </p>
              )}
            </div>

            {/* ── 5. EDUCATION & CERTIFICATIONS ── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

              {/* Education */}
              <div className="card" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                  <GraduationCap size={18} style={{ color: 'var(--pine)' }} />
                  <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Education</h3>
                </div>

                {cvDetail?.educations?.length ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {cvDetail.educations.map((edu, i) => (
                      <div key={i}>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--ink)' }}>{edu.degree}</div>
                        <div style={{ fontSize: '12.5px', color: 'var(--muted)' }}>{edu.institution} {edu.field && `(${edu.field})`}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>No education records parsed.</p>
                )}
              </div>

              {/* Certifications */}
              <div className="card" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                  <Award size={18} style={{ color: '#b97820' }} />
                  <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Certifications</h3>
                </div>

                {cvDetail?.certifications?.length ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {cvDetail.certifications.map((cert, i) => (
                      <div key={i}>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--ink)' }}>{cert.name}</div>
                        <div style={{ fontSize: '12.5px', color: 'var(--muted)' }}>{cert.issuer}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>No certifications recorded.</p>
                )}
              </div>

            </div>

          </div>
        )}

      </div>
    </CandidateShell>
  );
}

const labelStyle = {
  display: 'block', fontSize: '12px', fontWeight: 700,
  color: 'var(--ink)', marginBottom: '4px'
};

const inputStyle = {
  width: '100%', padding: '9px 12px',
  border: '1.5px solid var(--line)', borderRadius: '8px',
  fontSize: '13.5px', color: 'var(--ink)', background: '#fff',
  outline: 'none', boxSizing: 'border-box'
};

const infoItemStyle = {
  display: 'flex', alignItems: 'center', gap: '10px',
  background: 'var(--soft)', padding: '10px 14px', borderRadius: '8px'
};
