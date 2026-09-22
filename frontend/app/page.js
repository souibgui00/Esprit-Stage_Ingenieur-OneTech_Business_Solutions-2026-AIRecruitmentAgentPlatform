'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import CandidateShell from '../components/layout/CandidateShell';
import { homeApi } from '../lib/api/home';
import { ErrorState, JobCard, LoadingState, StatusBadge } from '../components/ui';
import {
  Upload, ArrowRight, CheckCircle, Clock, Bell,
  Briefcase, FileText, Sparkles, TrendingUp, Zap,
  ChevronRight, AlertCircle, Shield
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   HELPERS
───────────────────────────────────────────────────────────── */
const fmtDate = (d) =>
  d ? new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(d)) : '';

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

/* IntersectionObserver reveal — fires once */
function useReveal(threshold = 0.1) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setVisible(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, visible];
}

/* ─────────────────────────────────────────────────────────────
   HERO ILLUSTRATION — CV → AI → Opportunities pipeline
───────────────────────────────────────────────────────────── */
function HeroPipeline() {
  return (
    <svg
      className="dash-hero-svg"
      viewBox="0 0 400 280"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* ── Ambient glow ── */}
      <circle cx="340" cy="80"  r="140" fill="rgba(111,207,151,0.07)" />
      <circle cx="200" cy="140" r="100" fill="rgba(111,207,151,0.05)" />
      <circle cx="60"  cy="220" r="80"  fill="rgba(111,207,151,0.04)" />

      {/* ── CV / Document node (left) ── */}
      <g style={{animation:'float-node 5s ease-in-out 0s infinite'}}>
        <rect x="22" y="90" width="56" height="72" rx="7"
          fill="rgba(255,255,255,0.06)" stroke="rgba(111,207,151,0.35)" strokeWidth="1.2" />
        {/* Document lines */}
        <line x1="32" y1="108" x2="68" y2="108" stroke="rgba(111,207,151,0.5)"  strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="32" y1="118" x2="68" y2="118" stroke="rgba(111,207,151,0.35)" strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="32" y1="128" x2="58" y2="128" stroke="rgba(111,207,151,0.25)" strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="32" y1="138" x2="64" y2="138" stroke="rgba(111,207,151,0.2)"  strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="32" y1="148" x2="50" y2="148" stroke="rgba(111,207,151,0.15)" strokeWidth="1.5" strokeLinecap="round"/>
        {/* CV label chip */}
        <rect x="28" y="93" width="22" height="10" rx="3" fill="rgba(111,207,151,0.3)"/>
        <text x="39" y="101" fontSize="6" fill="rgba(111,207,151,0.95)" textAnchor="middle" fontWeight="700">CV</text>
      </g>
      <text x="50" y="176" fontSize="9" fill="rgba(255,255,255,0.3)" textAnchor="middle" fontWeight="500">Your profile</text>

      {/* ── Connection: CV → AI hub ── */}
      <line x1="78" y1="126" x2="164" y2="140"
        stroke="rgba(111,207,151,0.25)" strokeWidth="1" fill="none"
        strokeDasharray="100" style={{animation:'draw-line 2.5s ease 0.3s both'}} />
      {/* Traveling particle */}
      <circle r="2.5" fill="rgba(111,207,151,0.7)" style={{animation:'travel-h 3s ease-in-out 1.5s infinite'}}>
        <animateMotion dur="3s" begin="1.5s" repeatCount="indefinite"
          path="M78,126 L164,140" />
      </circle>

      {/* ── AI Hub (center) ── */}
      {/* Outer pulse rings */}
      <circle cx="196" cy="140" r="42" stroke="rgba(111,207,151,0.08)" strokeWidth="1" fill="none"
        style={{animation:'pulse-ring 3.2s ease-in-out infinite'}} />
      <circle cx="196" cy="140" r="30" stroke="rgba(111,207,151,0.12)" strokeWidth="1" fill="none"
        style={{animation:'pulse-ring 3.2s ease-in-out 0.8s infinite'}} />
      {/* Hub body */}
      <circle cx="196" cy="140" r="22"
        fill="rgba(111,207,151,0.15)" stroke="rgba(111,207,151,0.5)" strokeWidth="1.5"
        style={{animation:'float-node 4s ease-in-out 0.2s infinite'}} />
      <circle cx="196" cy="140" r="14"
        fill="rgba(111,207,151,0.25)"
        style={{animation:'float-node 4s ease-in-out 0.2s infinite'}} />
      {/* Sparkle / AI symbol */}
      <g style={{animation:'float-node 4s ease-in-out 0.2s infinite'}}>
        <line x1="196" y1="130" x2="196" y2="150" stroke="rgba(111,207,151,0.9)" strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="186" y1="140" x2="206" y2="140" stroke="rgba(111,207,151,0.9)" strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="189" y1="133" x2="203" y2="147" stroke="rgba(111,207,151,0.55)" strokeWidth="1" strokeLinecap="round"/>
        <line x1="203" y1="133" x2="189" y2="147" stroke="rgba(111,207,151,0.55)" strokeWidth="1" strokeLinecap="round"/>
      </g>
      <text x="196" y="174" fontSize="9" fill="rgba(255,255,255,0.35)" textAnchor="middle" fontWeight="600">AI engine</text>

      {/* ── Connections: AI hub → Job nodes ── */}
      <g stroke="rgba(111,207,151,0.22)" strokeWidth="1" fill="none">
        <line x1="218" y1="124" x2="300" y2="75"
          strokeDasharray="120" style={{animation:'draw-line 2.5s ease 0.7s both'}} />
        <line x1="220" y1="140" x2="305" y2="140"
          strokeDasharray="100" style={{animation:'draw-line 2.5s ease 0.9s both'}} />
        <line x1="218" y1="156" x2="300" y2="200"
          strokeDasharray="120" style={{animation:'draw-line 2.5s ease 1.1s both'}} />
      </g>
      {/* Particles toward jobs */}
      <circle r="2" fill="rgba(111,207,151,0.6)">
        <animateMotion dur="2.8s" begin="2s" repeatCount="indefinite"
          path="M218,124 L300,75" />
      </circle>
      <circle r="2" fill="rgba(111,207,151,0.6)">
        <animateMotion dur="2.8s" begin="2.6s" repeatCount="indefinite"
          path="M220,140 L305,140" />
      </circle>
      <circle r="2" fill="rgba(111,207,151,0.6)">
        <animateMotion dur="2.8s" begin="3.2s" repeatCount="indefinite"
          path="M218,156 L300,200" />
      </circle>

      {/* ── Job nodes (right) ── */}
      {/* Top job */}
      <g style={{animation:'float-node 4.8s ease-in-out 0.4s infinite'}}>
        <circle cx="318" cy="75" r="16"
          fill="rgba(255,255,255,0.05)" stroke="rgba(111,207,151,0.4)" strokeWidth="1.2" />
        <rect x="311" y="68" width="14" height="10" rx="2"
          fill="none" stroke="rgba(111,207,151,0.6)" strokeWidth="1"/>
        <line x1="312" y1="73" x2="325" y2="73" stroke="rgba(111,207,151,0.6)" strokeWidth="1" strokeLinecap="round"/>
        <rect x="314" y="65" width="8" height="3" rx="1" fill="rgba(111,207,151,0.4)"/>
      </g>

      {/* Middle job */}
      <g style={{animation:'float-node 5.5s ease-in-out 1.2s infinite'}}>
        <circle cx="322" cy="140" r="18"
          fill="rgba(111,207,151,0.1)" stroke="rgba(111,207,151,0.5)" strokeWidth="1.5" />
        <rect x="314" y="133" width="16" height="11" rx="2"
          fill="none" stroke="rgba(111,207,151,0.7)" strokeWidth="1.2"/>
        <line x1="315" y1="139" x2="330" y2="139" stroke="rgba(111,207,151,0.7)" strokeWidth="1.2" strokeLinecap="round"/>
        <rect x="317" y="130" width="10" height="3" rx="1" fill="rgba(111,207,151,0.5)"/>
        {/* match score badge */}
        <circle cx="334" cy="130" r="8" fill="rgba(21,91,61,0.8)" />
        <text x="334" y="133.5" fontSize="6" fill="#6fcf97" textAnchor="middle" fontWeight="700">94%</text>
      </g>

      {/* Bottom job */}
      <g style={{animation:'float-node 4.2s ease-in-out 2s infinite'}}>
        <circle cx="316" cy="205" r="15"
          fill="rgba(255,255,255,0.04)" stroke="rgba(111,207,151,0.32)" strokeWidth="1.2" />
        <rect x="309" y="199" width="13" height="9" rx="2"
          fill="none" stroke="rgba(111,207,151,0.5)" strokeWidth="1"/>
        <line x1="310" y1="204" x2="322" y2="204" stroke="rgba(111,207,151,0.5)" strokeWidth="1" strokeLinecap="round"/>
        <rect x="312" y="196" width="8" height="3" rx="1" fill="rgba(111,207,151,0.32)"/>
      </g>

      {/* Labels */}
      <text x="318" y="100" fontSize="8" fill="rgba(255,255,255,0.28)" textAnchor="middle">Role 1</text>
      <text x="358" y="144" fontSize="8" fill="rgba(255,255,255,0.28)" textAnchor="middle">Top match</text>
      <text x="316" y="230" fontSize="8" fill="rgba(255,255,255,0.22)" textAnchor="middle">Role 3</text>

      {/* ── Accent micro-dots ── */}
      <circle cx="148" cy="88"  r="2" fill="rgba(111,207,151,0.2)"
        style={{animation:'float-node 6s ease-in-out 0.5s infinite'}} />
      <circle cx="260" cy="112" r="1.5" fill="rgba(111,207,151,0.18)"
        style={{animation:'float-node 5.5s ease-in-out 1.8s infinite'}} />
      <circle cx="142" cy="195" r="2" fill="rgba(111,207,151,0.15)"
        style={{animation:'float-node 7s ease-in-out 3s infinite'}} />
      <circle cx="370" cy="175" r="1.5" fill="rgba(111,207,151,0.15)"
        style={{animation:'float-node 6.5s ease-in-out 1s infinite'}} />
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────
   AI MATCHING — animated empty state SVG
───────────────────────────────────────────────────────────── */
function AiScanningVisual() {
  return (
    <svg viewBox="0 0 280 120" className="dash-ai-scan-svg" aria-hidden="true">
      {/* Faint grid dots */}
      {[40,80,120,160,200,240].map(x =>
        [20,50,80,100].map(y => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="1.5"
            fill="rgba(111,207,151,0.15)" />
        ))
      )}
      {/* Scanning line */}
      <line x1="0" y1="60" x2="280" y2="60"
        stroke="rgba(111,207,151,0.35)" strokeWidth="1"
        style={{animation:'scan-line 2.8s ease-in-out infinite'}} />
      <rect x="0" y="54" width="280" height="12"
        fill="url(#scanGrad)" style={{animation:'scan-line 2.8s ease-in-out infinite'}} />
      <defs>
        <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(111,207,151,0)" />
          <stop offset="50%" stopColor="rgba(111,207,151,0.08)" />
          <stop offset="100%" stopColor="rgba(111,207,151,0)" />
        </linearGradient>
      </defs>
      {/* Pulsing data nodes */}
      {[
        {cx:60,cy:35,r:5,delay:'0s'},
        {cx:140,cy:60,r:7,delay:'0.4s'},
        {cx:220,cy:42,r:5,delay:'0.8s'},
        {cx:100,cy:88,r:4,delay:'1.2s'},
        {cx:190,cy:90,r:5,delay:'0.6s'},
      ].map((n,i) => (
        <g key={i}>
          <circle cx={n.cx} cy={n.cy} r={n.r + 5}
            fill="none" stroke="rgba(111,207,151,0.12)" strokeWidth="1"
            style={{animation:`pulse-ring 2.5s ease-in-out ${n.delay} infinite`}} />
          <circle cx={n.cx} cy={n.cy} r={n.r}
            fill="rgba(111,207,151,0.25)" stroke="rgba(111,207,151,0.5)" strokeWidth="1"
            style={{animation:`float-node 4s ease-in-out ${n.delay} infinite`}} />
        </g>
      ))}
      {/* Connecting lines */}
      <g stroke="rgba(111,207,151,0.15)" strokeWidth="0.8" fill="none">
        <line x1="60" y1="35" x2="140" y2="60" />
        <line x1="140" y1="60" x2="220" y2="42" />
        <line x1="140" y1="60" x2="100" y2="88" />
        <line x1="140" y1="60" x2="190" y2="90" />
      </g>
    </svg>
  );
}

/* ─────────────────────────────────────────────────────────────
   NEXT BEST ACTION
───────────────────────────────────────────────────────────── */
function nextAction(hasCV, cvReady, recs, apps, notifs) {
  const unreadCount = notifs.filter(n => n.is_read === false).length;
  if (!hasCV)   return { icon: Upload,     label: 'Start here',      title: 'Upload your CV to get started',       desc: 'Your CV is the engine of your job search. Once uploaded, AI matching, recommendations, and auto-apply all unlock.', href: '/cv/upload',     tone: 'action' };
  if (!cvReady) return { icon: Clock,      label: 'In progress',     title: 'Your CV is being analysed',           desc: 'Analysis usually takes a few minutes. Head to the CV page to check current status.',                             href: '/cv',            tone: 'processing' };
  if (recs.length > 0) {
    const top = recs[0];
    const score = top.match?.compatibility_score;
    return { icon: Sparkles, label: 'Top match', title: `${top.job_offer.title} at ${top.job_offer.company}`, desc: `${score ? `${Math.round(score)}% compatibility — ` : ''}Explore this opportunity and apply in one click.`, href: `/jobs/${top.job_offer.id}`, tone: 'match' };
  }
  if (apps.length > 0) return { icon: Briefcase,  label: 'Pipeline',        title: 'You have active applications',        desc: 'Stay on top of your pipeline — check for status updates and next steps.',                                       href: '/applications',  tone: 'apps' };
  if (unreadCount > 0) return { icon: Bell,        label: `${unreadCount} unread`, title: 'You have new notifications', desc: 'The platform has something for you. Check your notifications for updates.',                                  href: '/notifications', tone: 'notif' };
  return { icon: TrendingUp, label: 'Explore',          title: 'Discover new opportunities',          desc: 'Browse the latest curated jobs and find roles that match your skills and goals.',                                              href: '/jobs',          tone: 'explore' };
}

function NextBestAction({ action }) {
  const Icon = action.icon;
  return (
    <Link href={action.href} className={`dash-nba dash-nba--${action.tone}`}>
      <div className="dash-nba-icon">
        <Icon size={20} />
      </div>
      <div className="dash-nba-body">
        <span className="dash-nba-eyebrow">{action.label}</span>
        <strong className="dash-nba-title">{action.title}</strong>
        <p className="dash-nba-desc">{action.desc}</p>
      </div>
      <span className="dash-nba-arrow"><ArrowRight size={18} /></span>
    </Link>
  );
}

/* ─────────────────────────────────────────────────────────────
   CV STATUS STRIP — with animated indicators
───────────────────────────────────────────────────────────── */
function CvStrip({ hasCV, cvReady }) {
  if (!hasCV) return (
    <div className="dash-cv-strip dash-cv-strip--missing">
      <div className="dash-cv-strip-icon">
        <Upload size={17} />
        <span className="dash-cv-badge dash-cv-badge--missing">!</span>
      </div>
      <div className="dash-cv-strip-body">
        <strong>No CV uploaded</strong>
        <span>Unlock AI matching, recommendations, and auto-apply by uploading your CV.</span>
      </div>
      <Link className="button primary" href="/cv/upload" style={{ fontSize: 13, whiteSpace: 'nowrap' }}>
        Upload CV
      </Link>
    </div>
  );
  if (cvReady) return (
    <div className="dash-cv-strip dash-cv-strip--ready">
      <div className="dash-cv-strip-icon">
        <CheckCircle size={17} />
        <span className="dash-cv-badge dash-cv-badge--ready" aria-hidden="true" />
      </div>
      <div className="dash-cv-strip-body">
        <strong>CV active</strong>
        <span>Your profile is live and being matched with opportunities in real time.</span>
      </div>
      <Link className="button secondary" href="/cv" style={{ fontSize: 13, whiteSpace: 'nowrap' }}>
        Review CV <ChevronRight size={13} />
      </Link>
    </div>
  );
  return (
    <div className="dash-cv-strip dash-cv-strip--processing">
      <div className="dash-cv-strip-icon">
        <Clock size={17} />
        <span className="dash-cv-badge dash-cv-badge--processing" aria-hidden="true" />
      </div>
      <div className="dash-cv-strip-body">
        <strong>Analysing your CV</strong>
        <span>Our AI is reading your profile — recommendations will appear shortly.</span>
      </div>
      <Link className="button secondary" href="/cv" style={{ fontSize: 13, whiteSpace: 'nowrap' }}>
        View status
      </Link>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   SECTION WRAPPER — scroll reveal
───────────────────────────────────────────────────────────── */
function Section({ className = '', delay = 0, children }) {
  const [ref, visible] = useReveal();
  return (
    <section
      ref={ref}
      className={`dash-section ${visible ? 'revealed' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────
   CONTEXTUAL HERO TEXT
───────────────────────────────────────────────────────────── */
function heroContext(hasCV, cvReady, recs, apps) {
  if (!hasCV)        return 'Upload your CV to unlock AI-powered matching, personalised recommendations, and one-click apply.';
  if (!cvReady)      return 'Your CV is being analysed. This usually takes a few minutes — recommendations will appear shortly.';
  if (recs.length > 0) return `${recs.length} opportunit${recs.length > 1 ? 'ies are' : 'y is'} matched to your profile. Your strongest results are ready to explore.`;
  if (apps.length > 0) return `You have ${apps.length} active application${apps.length > 1 ? 's' : ''}. Stay on top of your pipeline and check for updates.`;
  return 'Your workspace is ready. Explore opportunities and track every application from one place.';
}

/* ─────────────────────────────────────────────────────────────
   FEED ITEMS
───────────────────────────────────────────────────────────── */
function AppItem({ app, idx }) {
  return (
    <Link href="/applications" className="dash-feed-item" style={{ animationDelay: `${idx * 55}ms` }}>
      <div className="dash-feed-icon"><Briefcase size={14} /></div>
      <div className="dash-feed-body">
        <span className="dash-feed-title">{app.match_details?.job_title || 'Opportunity'}</span>
        <span className="dash-feed-meta">{app.match_details?.company || '—'} · {fmtDate(app.created_at)}</span>
      </div>
      <StatusBadge status={app.status} />
    </Link>
  );
}

function NotifItem({ n, idx }) {
  return (
    <Link
      href="/notifications"
      className={`dash-feed-item${n.is_read === false ? ' dash-notif--unread' : ''}`}
      style={{ animationDelay: `${idx * 55}ms` }}
    >
      <div className={`dash-feed-icon${n.is_read === false ? ' dash-feed-icon--notif' : ''}`}>
        <Bell size={14} />
      </div>
      <div className="dash-feed-body">
        <span className="dash-feed-title">{n.message}</span>
        <span className="dash-feed-meta">{fmtDate(n.created_at)}</span>
      </div>
      {n.is_read === false && <span className="dash-notif-dot" aria-label="Unread" />}
    </Link>
  );
}

/* ─────────────────────────────────────────────────────────────
   EMPTY FEED STATE
───────────────────────────────────────────────────────────── */
function EmptyFeed({ icon: Icon, message, action }) {
  return (
    <div className="dash-empty-feed">
      {Icon && <div className="dash-empty-feed-icon"><Icon size={22} /></div>}
      <p>{message}</p>
      {action}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   BOTTOM INFO BAR
───────────────────────────────────────────────────────────── */
function BottomInfoBar({ hasCV, cvReady, recCount, unread }) {
  return (
    <div className="dash-info-bar dash-enter" style={{ animationDelay: '300ms' }}>
      <div className="dash-info-left">
        <span className="dash-info-pulse-dot" />
        <span className="dash-info-label">AI-powered recruitment</span>
      </div>
      <div className="dash-info-pills">
        <span className={`dash-info-pill ${cvReady ? 'dash-info-pill--green' : hasCV ? 'dash-info-pill--amber' : 'dash-info-pill--gray'}`}>
          <FileText size={11} />
          CV {cvReady ? 'ready' : hasCV ? 'processing' : 'missing'}
        </span>
        {recCount > 0 && (
          <span className="dash-info-pill dash-info-pill--green">
            <Sparkles size={11} />
            {recCount} match{recCount !== 1 ? 'es' : ''}
          </span>
        )}
        {unread > 0 && (
          <span className="dash-info-pill dash-info-pill--amber">
            <Bell size={11} />
            {unread} unread
          </span>
        )}
        <span className="dash-info-pill dash-info-pill--gray">
          <Shield size={11} />
          Private &amp; secure
        </span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   MAIN PAGE
───────────────────────────────────────────────────────────── */
export default function Home() {
  const [data, setData]   = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    homeApi.summary()
      .then(setData)
      .catch(() => setError('We could not load your workspace. Please try again.'));
  }, []);

  if (error) return (
    <CandidateShell>
      <div className="page">
        <div className="dash-error">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      </div>
    </CandidateShell>
  );

  if (!data) return (
    <CandidateShell>
      <div className="page dash-loading">
        <div className="dash-loading-inner">
          <div className="dash-loading-ring" />
          <span>Loading your workspace…</span>
        </div>
      </div>
    </CandidateShell>
  );

  const cv      = data.cv;
  const name    = cv?.personal_info?.full_name?.split(' ')[0];
  const hasCV   = !!cv;
  const cvReady = cv?.status === 'PARSED';
  const recs    = (data.recommendations || []).slice(0, 3);
  const apps    = (data.applications    || []).slice(0, 3);
  const notifs  = (data.notifications   || []).slice(0, 4);
  const unread  = (data.notifications || []).filter(n => n.is_read === false).length;
  const action  = nextAction(hasCV, cvReady, data.recommendations || [], apps, data.notifications || []);

  return (
    <CandidateShell>
      <div className="page dash-page">

        {/* ── HERO ────────────────────────────────────────────── */}
        <section className="dash-hero dash-enter">
          {/* Decorative bg radial */}
          <div className="dash-hero-bg-glow" aria-hidden="true" />

          <div className="dash-hero-left">
            <p className="dash-hero-eyebrow">{greeting()}</p>
            <h1 className="dash-hero-title">
              {name
                ? <>Welcome back, <span className="dash-hero-name">{name}.</span></>
                : 'Your workspace is ready.'}
            </h1>
            <p className="dash-hero-subtitle">
              {heroContext(hasCV, cvReady, data.recommendations || [], apps)}
            </p>
            <div className="dash-hero-actions">
              <Link
                className="button primary dash-hero-cta"
                href={!hasCV ? '/cv/upload' : recs.length > 0 ? '/jobs' : '/cv'}
              >
                {!hasCV
                  ? <><Upload size={15} /> Upload your CV</>
                  : recs.length > 0
                    ? <>Explore opportunities <ArrowRight size={15} /></>
                    : <><FileText size={15} /> Review my CV</>}
              </Link>
              {hasCV && recs.length > 0 && (
                <Link className="button dash-hero-ghost" href="/cv">
                  <FileText size={14} /> My profile
                </Link>
              )}
            </div>
          </div>

          <div className="dash-hero-visual" aria-hidden="true">
            <HeroPipeline />
          </div>
        </section>

        {/* ── CV STRIP ────────────────────────────────────────── */}
        <div className="dash-enter dash-enter--1">
          <CvStrip hasCV={hasCV} cvReady={cvReady} />
        </div>

        {/* ── NEXT BEST ACTION ────────────────────────────────── */}
        <Section delay={0} className="dash-section--nba">
          <div className="dash-section-head">
            <p className="eyebrow">
              <Zap size={11} style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
              Suggested action
            </p>
          </div>
          <NextBestAction action={action} />
        </Section>

        {/* ── RECOMMENDATIONS ─────────────────────────────────── */}
        <Section delay={40}>
          <div className="dash-section-head">
            <div>
              <p className="eyebrow" style={{ display:'flex', alignItems:'center', gap:4 }}>
                <Sparkles size={11} /> Your AI Recruitment Agent
              </p>
              <h2 className="section-title">Top Opportunities For You</h2>
            </div>
            {recs.length > 0 && (
              <Link className="dash-view-all" href="/jobs">
                Explore all recommendations <ArrowRight size={13} />
              </Link>
            )}
          </div>

          {recs.length > 0 ? (
            <div className="grid recommendations dash-recs">
              {recs.map((item, i) => (
                <div key={item.match.id} className="dash-rec-wrap" style={{ animationDelay: `${i * 80}ms` }}>
                  <JobCard job={item.job_offer} match={item.match} />
                </div>
              ))}
            </div>
          ) : (
            <div className="dash-empty-recs">
              <AiScanningVisual />
              <div className="dash-empty-recs-body">
                {!hasCV ? (
                  <>
                    <h3>Upload your CV to unlock AI recommendations</h3>
                    <p>Your AI recruitment agent will analyze your CV and automatically rank the most compatible opportunities for you.</p>
                    <Link className="button primary" href="/cv/upload"><Upload size={14} /> Upload your CV</Link>
                  </>
                ) : (
                  <>
                    <h3>Your AI agent is ranking opportunities</h3>
                    <p>Compatibility is being evaluated for available roles. Your ranked recommendations will appear here shortly.</p>
                    <Link className="dash-quiet-link" href="/jobs">Open Discover <ArrowRight size={13} /></Link>
                  </>
                )}
              </div>
            </div>
          )}
        </Section>

        {/* ── ACTIVITY + NOTIFICATIONS ────────────────────────── */}
        <Section delay={80} className="grid two-col">

          <div className="card dash-feed-card">
            <div className="dash-feed-header">
              <div>
                <p className="eyebrow" style={{ marginBottom:2 }}>
                  <Briefcase size={11} style={{ display:'inline', verticalAlign:'middle', marginRight:3 }} />
                  Recent activity
                </p>
                <h2 className="dash-feed-card-title">Applications</h2>
              </div>
              <Link className="dash-view-all" href="/applications">
                View all <ArrowRight size={13} />
              </Link>
            </div>
            {apps.length > 0 ? (
              <div className="dash-feed">
                {apps.map((app, i) => <AppItem key={app.id} app={app} idx={i} />)}
              </div>
            ) : (
              <EmptyFeed
                icon={Briefcase}
                message="No applications yet. Once you start tracking opportunities they'll appear here."
                action={
                  <Link className="dash-quiet-link" href="/jobs">
                    Explore opportunities <ArrowRight size={13} />
                  </Link>
                }
              />
            )}
          </div>

          <div className="card dash-feed-card">
            <div className="dash-feed-header">
              <div>
                <p className="eyebrow" style={{ marginBottom:2 }}>
                  <Bell size={11} style={{ display:'inline', verticalAlign:'middle', marginRight:3 }} />
                  {unread > 0 ? `${unread} unread` : 'Latest'}
                </p>
                <h2 className="dash-feed-card-title">Notifications</h2>
              </div>
              <Link className="dash-view-all" href="/notifications">
                View all <ArrowRight size={13} />
              </Link>
            </div>
            {notifs.length > 0 ? (
              <div className="dash-feed">
                {notifs.map((n, i) => <NotifItem key={n.id} n={n} idx={i} />)}
              </div>
            ) : (
              <EmptyFeed
                icon={Bell}
                message="You're all caught up. Notifications will appear here when the platform has something to share."
              />
            )}
          </div>

        </Section>

        {/* ── BOTTOM INFO BAR ─────────────────────────────────── */}
        <BottomInfoBar
          hasCV={hasCV}
          cvReady={cvReady}
          recCount={recs.length}
          unread={unread}
        />

      </div>
    </CandidateShell>
  );
}