'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import CandidateShell from '../../components/layout/CandidateShell';
import { cvApi } from '../../lib/api/cv';
import {
  FileText, Upload, CheckCircle2, Clock, AlertCircle, ArrowRight,
  Briefcase, GraduationCap, Award, Wrench, User, Sparkles, RefreshCw
} from 'lucide-react';

export default function CVPage() {
  const [cvs, setCvs] = useState(null);
  const [cvDetail, setCvDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadCV() {
      setLoading(true);
      setError('');
      try {
        const cvList = await cvApi.list();
        setCvs(cvList || []);

        if (cvList && cvList.length > 0) {
          const activeCv = cvList[0];
          if (activeCv.status === 'PARSED') {
            const detail = await cvApi.get(activeCv.id);
            setCvDetail(detail);
          }
        }
      } catch (err) {
        console.error('Failed to load CV profile:', err);
        setError('Could not load your CV profile. Please refresh the page.');
      } finally {
        setLoading(false);
      }
    }
    loadCV();
  }, []);

  const activeCv = cvs?.[0];
  const personal = cvDetail?.personal_info;

  return (
    <CandidateShell>
      <div className="page" style={{ maxWidth: '880px' }}>

        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <p className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <FileText size={12} /> Active CV Document
          </p>
          <h1 style={{ fontSize: 'clamp(28px, 4vw, 40px)', fontWeight: 800, letterSpacing: '-0.04em', margin: '0 0 10px', color: 'var(--ink)' }}>
            My CV & Profile
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: '15px', margin: 0 }}>
            Your active CV document is analyzed by the AI recruitment agent to evaluate opportunity matching.
          </p>
        </div>

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
            {[1, 2, 3].map(i => (
              <div key={i} className="card" style={{ height: '140px', background: 'var(--soft)', animation: 'shimmer 1.5s infinite' }} />
            ))}
          </div>
        ) : !activeCv ? (
          /* ── NO CV UPLOADED STATE ── */
          <div className="card" style={{ padding: '40px 28px', textAlign: 'center', background: 'linear-gradient(135deg, #f8fdf9 0%, #ffffff 100%)' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '50%', background: 'var(--mint)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px'
            }}>
              <FileText size={30} style={{ color: 'var(--pine)' }} />
            </div>
            <h2 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 8px', color: 'var(--ink)' }}>
              No Active CV Uploaded
            </h2>
            <p style={{ color: 'var(--muted)', fontSize: '14.5px', maxWidth: '480px', margin: '0 auto 24px', lineHeight: 1.5 }}>
              Upload your PDF resume so the AI recruitment agent can extract your skills, experience, and match you with relevant opportunities.
            </p>
            <Link href="/cv/upload" className="button primary" style={{ padding: '11px 24px', fontSize: '15px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
              <Upload size={16} /> Upload Your CV
            </Link>
          </div>
        ) : (
          /* ── ACTIVE CV PRESENT STATE ── */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

            {/* Document Status Banner */}
            <div className="card" style={{ padding: '24px', background: activeCv.status === 'PARSED' ? '#f0fdf4' : activeCv.status === 'FAILED' ? '#fff1f2' : '#fffbeb', border: `1.5px solid ${activeCv.status === 'PARSED' ? '#bbf7d0' : activeCv.status === 'FAILED' ? '#fecdd3' : '#fde68a'}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      fontSize: '12px', fontWeight: 700, padding: '3px 10px', borderRadius: '999px',
                      background: activeCv.status === 'PARSED' ? '#dcfce7' : activeCv.status === 'FAILED' ? '#ffe4e6' : '#fef3c7',
                      color: activeCv.status === 'PARSED' ? '#166534' : activeCv.status === 'FAILED' ? '#9f1239' : '#b45309',
                    }}>
                      {activeCv.status === 'PARSED' ? <CheckCircle2 size={13} /> : activeCv.status === 'FAILED' ? <AlertCircle size={13} /> : <Clock size={13} />}
                      {activeCv.status === 'PARSED' ? '1 Active CV · Ready for Matching' : activeCv.status === 'FAILED' ? 'Parsing Failed' : 'Processing CV…'}
                    </span>
                  </div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '4px 0 2px', color: 'var(--ink)' }}>
                    {activeCv.filename || 'Resume Document'}
                  </h2>
                  <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>
                    Uploaded on {new Date(activeCv.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <Link href="/cv/upload" className="button primary" style={{ fontSize: '13px', padding: '9px 18px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <RefreshCw size={14} /> Replace CV
                  </Link>
                </div>
              </div>

              {activeCv.status === 'PARSED' && (
                <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #bbf7d0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <span style={{ fontSize: '13px', color: '#15803d', fontWeight: 600 }}>
                    ✨ Your CV is fully parsed and ready for AI compatibility ranking.
                  </span>
                  <Link href="/jobs" className="button secondary" style={{ fontSize: '12.5px', padding: '6px 14px', background: '#fff', color: '#166534', borderColor: '#bbf7d0', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    View Ranked Opportunities <ArrowRight size={13} />
                  </Link>
                </div>
              )}
            </div>

            {/* Single CV Policy Notice */}
            <div style={{ fontSize: '12.5px', color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '6px', padding: '0 4px' }}>
              <Sparkles size={13} style={{ color: 'var(--pine)' }} />
              <span>You maintain 1 active CV. Uploading a new PDF will automatically update your profile and recalculate match scores.</span>
            </div>

            {/* ── PARSED CV DETAILS Breakdown ── */}
            {activeCv.status === 'PARSED' && cvDetail && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                {/* Candidate Summary */}
                {personal && (
                  <div className="card" style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '12px' }}>
                      <User size={18} style={{ color: 'var(--pine)' }} />
                      <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Extracted Candidate Information</h3>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: 'var(--soft)', padding: '16px', borderRadius: '10px' }}>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 700, textTransform: 'uppercase' }}>Full Name</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px' }}>{personal.full_name || 'Not specified'}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 700, textTransform: 'uppercase' }}>Email</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px' }}>{personal.email || 'Not specified'}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 700, textTransform: 'uppercase' }}>Phone</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px' }}>{personal.phone || 'Not specified'}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 700, textTransform: 'uppercase' }}>Location</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px' }}>{personal.location || 'Not specified'}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Technical Skills */}
                <div className="card" style={{ padding: '24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                    <Wrench size={18} style={{ color: 'var(--pine)' }} />
                    <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>
                      Extracted Technical Skills ({cvDetail.skills?.length || 0})
                    </h3>
                  </div>

                  {cvDetail.skills?.length ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {cvDetail.skills.map((s, i) => (
                        <span key={i} style={{
                          background: 'var(--mint)', color: 'var(--pine-dark)',
                          border: '1px solid #b6dcc2', borderRadius: '999px',
                          padding: '6px 14px', fontSize: '13px', fontWeight: 700
                        }}>
                          {s.canonical_name || s.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>No skills extracted.</p>
                  )}
                </div>

                {/* Work Experience */}
                <div className="card" style={{ padding: '24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
                    <Briefcase size={18} style={{ color: '#b45309' }} />
                    <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>
                      Parsed Experience ({cvDetail.experiences?.length || 0})
                    </h3>
                  </div>

                  {cvDetail.experiences?.length ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {cvDetail.experiences.map((exp, i) => (
                        <div key={i} style={{ borderLeft: '3px solid var(--pine)', paddingLeft: '14px' }}>
                          <div style={{ fontWeight: 800, fontSize: '15px', color: 'var(--ink)' }}>{exp.title}</div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted)', margin: '2px 0 4px' }}>
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
                    <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>No experience records parsed.</p>
                  )}
                </div>

                {/* Education & Certifications */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                  <div className="card" style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                      <GraduationCap size={16} style={{ color: 'var(--pine)' }} />
                      <h4 style={{ fontSize: '14.5px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Education</h4>
                    </div>
                    {cvDetail.educations?.length ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {cvDetail.educations.map((edu, i) => (
                          <div key={i}>
                            <div style={{ fontWeight: 700, fontSize: '13.5px', color: 'var(--ink)' }}>{edu.degree}</div>
                            <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{edu.institution} {edu.field && `(${edu.field})`}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>No education parsed.</p>
                    )}
                  </div>

                  <div className="card" style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                      <Award size={16} style={{ color: '#b97820' }} />
                      <h4 style={{ fontSize: '14.5px', fontWeight: 800, margin: 0, color: 'var(--ink)' }}>Certifications</h4>
                    </div>
                    {cvDetail.certifications?.length ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {cvDetail.certifications.map((cert, i) => (
                          <div key={i}>
                            <div style={{ fontWeight: 700, fontSize: '13.5px', color: 'var(--ink)' }}>{cert.name}</div>
                            <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{cert.issuer}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>No certifications parsed.</p>
                    )}
                  </div>

                </div>

              </div>
            )}

          </div>
        )}
      </div>

      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </CandidateShell>
  );
}
