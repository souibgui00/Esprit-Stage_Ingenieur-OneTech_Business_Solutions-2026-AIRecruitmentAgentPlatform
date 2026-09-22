'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import CandidateShell from '../../components/layout/CandidateShell';
import { cvApi } from '../../lib/api/cv';
import { matchingApi } from '../../lib/api/matching';
import { jobsApi } from '../../lib/api/jobs';
import { authApi } from '../../lib/api/auth';
import { getMatchLabel } from '../../components/ui';
import {
  Sparkles, FileText, Clock, Zap, ChevronRight, AlertCircle,
  Briefcase, MapPin, Search, SlidersHorizontal,
  X, RefreshCw, Target, TrendingUp, RotateCcw
} from 'lucide-react';

/* ── helpers ───────────────────────────────────────────────── */
const SOURCE_LABELS = {
  remotive: 'Remotive', arbeitnow: 'Arbeitnow', jobicy: 'Jobicy',
  themuse: 'The Muse', bundesagentur: 'Bundesagentur',
  welcometothejungle: 'WTTJ', linkedin: 'LinkedIn', platform: 'Platform',
};

function scoreColor(score) {
  if (score >= 85) return 'var(--pine)';
  if (score >= 75) return '#16a34a';
  if (score >= 60) return '#ca8a04';
  return '#dc2626';
}

/* ── Circular mini gauge ────────────────────────────────────── */
function ScoreDial({ score }) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const filled = Math.max(0, Math.min(circ, (score / 100) * circ));
  const color = scoreColor(score);
  return (
    <div className="disc-dial">
      <svg width={56} height={56} viewBox="0 0 56 56">
        <circle cx={28} cy={28} r={r} fill="none" stroke="var(--line)" strokeWidth={5} />
        <circle
          cx={28} cy={28} r={r} fill="none"
          stroke={color} strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeDashoffset={circ / 4}
          style={{ transition: 'stroke-dasharray 0.7s ease' }}
        />
      </svg>
      <div className="disc-dial-inner">
        <span className="disc-dial-num" style={{ color }}>{Math.round(score)}</span>
        <span className="disc-dial-pct">%</span>
      </div>
    </div>
  );
}

/* ── Recommendation card ────────────────────────────────────── */
function RecommendationCard({ match, job, idx, userPrefs }) {
  const score = match.compatibility_score ?? 0;
  const label = getMatchLabel(score);
  const color = scoreColor(score);

  const isAutoApply = userPrefs?.application_mode === 'AUTO_APPLY';
  const minScore = userPrefs?.min_match_score ?? 80;
  const isEligible = isAutoApply && score >= minScore;

  return (
    <Link
      href={`/jobs/${job.id}`}
      className="disc-rec-card"
      style={{ '--card-delay': `${idx * 60}ms` }}
    >
      <div className="disc-rec-left">
        <ScoreDial score={score} />
      </div>

      <div className="disc-rec-body">
        <div className="disc-rec-head">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
              <span className="disc-rec-label" style={{ color }}>
                {label}
              </span>
              {isAutoApply ? (
                isEligible ? (
                  <span style={{ background: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0', padding: '2px 8px', borderRadius: '999px', fontSize: '10.5px', fontWeight: 700 }}>
                    ✓ Eligible for Auto-Apply
                  </span>
                ) : (
                  <span style={{ background: '#fff1f2', color: '#9f1239', border: '1px solid #fecdd3', padding: '2px 8px', borderRadius: '999px', fontSize: '10.5px', fontWeight: 600 }}>
                    Below Auto-Apply Threshold ({minScore}%)
                  </span>
                )
              ) : (
                <span style={{ background: 'var(--mint)', color: 'var(--pine-dark)', padding: '2px 8px', borderRadius: '999px', fontSize: '10.5px', fontWeight: 700 }}>
                  👤 AI Recommended
                </span>
              )}
            </div>
            <h3 className="disc-rec-title">{job.title}</h3>
          </div>
          <span className="disc-rec-src">
            {SOURCE_LABELS[job.source_name] || job.source_name || 'Platform'}
          </span>
        </div>

        <p className="disc-rec-company">
          <strong>{job.company}</strong>
          {job.location && <span> · <MapPin size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> {job.location}</span>}
          {job.contract_type && <span> · <Briefcase size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> {job.contract_type}</span>}
        </p>

        {match.summary && (
          <p className="disc-rec-summary">
            <Sparkles size={11} className="disc-rec-sparkle" />
            {match.summary}
          </p>
        )}

        {match.matching_points?.length > 0 && (
          <div className="disc-rec-points">
            {match.matching_points.slice(0, 3).map((pt, i) => (
              <span key={i} className="disc-rec-point">{pt}</span>
            ))}
          </div>
        )}
      </div>

      <div className="disc-rec-arrow">
        <ChevronRight size={18} />
      </div>
    </Link>
  );
}

/* ── Discovery card (unscored) ──────────────────────────────── */
function DiscoveryCard({ job }) {
  return (
    <Link href={`/jobs/${job.id}`} className="disc-new-card">
      <div className="disc-new-card-body">
        <p className="disc-new-title">{job.title}</p>
        <p className="disc-new-meta">
          {job.company}
          {job.location && ` · ${job.location}`}
          {job.contract_type && ` · ${job.contract_type}`}
        </p>
      </div>
      <span className="disc-pending-chip">
        <Clock size={10} /> Not evaluated
      </span>
    </Link>
  );
}

/* ── Score category group ───────────────────────────────────── */
function CategoryGroup({ label, emoji, items, renderItem }) {
  if (!items || !items.length) return null;
  return (
    <div className="disc-category">
      <h3 className="disc-category-head">
        <span>{emoji}</span> {label}
        <span className="disc-category-count">{items.length}</span>
      </h3>
      <div className="disc-category-list">
        {items.map(renderItem)}
      </div>
    </div>
  );
}

/* ── Skeleton loading ───────────────────────────────────────── */
function SkeletonFeed() {
  return (
    <div className="disc-skeleton-feed">
      <div className="disc-ai-status">
        <div className="disc-ai-dot disc-ai-dot--pulse" />
        <Sparkles size={13} />
        <span>AI agent is ranking opportunities for you…</span>
        <div className="disc-phase-spinner" />
      </div>
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="disc-skeleton-card" style={{ animationDelay: `${i * 100}ms` }}>
          <div className="disc-skel-circle" />
          <div className="disc-skel-lines">
            <div className="disc-skel-line disc-skel-line--title" />
            <div className="disc-skel-line disc-skel-line--sub" />
            <div className="disc-skel-line disc-skel-line--tag" />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN PAGE
═══════════════════════════════════════════════════════════════ */
export default function Jobs() {
  const [cv, setCv]                     = useState(null);
  const [cvLoaded, setCvLoaded]         = useState(false);
  const [userPrefs, setUserPrefs]       = useState(null);
  const [recommendations, setRecs]      = useState([]);
  const [discoveries, setDiscoveries]   = useState([]);
  const [totalOffers, setTotalOffers]   = useState(null);
  const [relevantOffers, setRelevantOffers] = useState(null);
  const [sourcingActive, setSourcingActive] = useState(false);
  const [sourcingTriggered, setSourcingTriggered] = useState(false);
  const [triggeringSourcing, setTriggeringSourcing] = useState(false);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');
  const [searchQuery, setSearchQuery]   = useState('');
  const [location, setLocation]         = useState('');
  const [contract, setContract]         = useState('');
  const [filtersOpen, setFiltersOpen]   = useState(false);
  const [searching, setSearching]       = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const inputRef = useRef(null);

  /* ── Load CV + primary ranked feed ──────────────────────── */
  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // 1. Fetch user's CV list
      let cvs = [];
      try {
        cvs = await cvApi.list();
      } catch (cvErr) {
        if (cvErr.response?.status === 401) {
          window.location.href = '/login';
          return;
        }
        cvs = [];
      }
      setCvLoaded(true);

      if (!cvs || !Array.isArray(cvs) || cvs.length === 0) {
        setCv(null);
        setLoading(false);
        return;
      }

      const activeCv = cvs[0];
      setCv(activeCv);

      if (!activeCv || activeCv.status !== 'PARSED') {
        setLoading(false);
        return;
      }

      // 2. Fetch user preferences (for agent autonomy & search criteria)
      let prefs = null;
      try {
        prefs = await authApi.getPreferences();
        setUserPrefs(prefs);
      } catch (_) {}

      // 3. Fetch inventory status (differentiates global vs user-relevant inventory)
      const queryKw = (prefs?.target_roles && prefs.target_roles.length > 0)
        ? prefs.target_roles.join(' ')
        : (prefs?.job_keywords || '');

      let invStatus = null;
      try {
        invStatus = await jobsApi.getStatus(queryKw ? { keywords: queryKw } : {});
        setTotalOffers(invStatus?.total_offers ?? 0);
        setRelevantOffers(invStatus?.relevant_offers ?? 0);
        setSourcingActive(invStatus?.sourcing_active ?? false);
      } catch (_) {}

      // Auto-trigger sourcing if NO RELEVANT INVENTORY exists for user's target criteria
      const isNoRelevant = (invStatus?.relevant_offers ?? 0) === 0;
      if (isNoRelevant && !invStatus?.sourcing_active) {
        try {
          await matchingApi.triggerSourcing(activeCv.id);
          setSourcingTriggered(true);
          setSourcingActive(true);
        } catch (_) {}
      }

      // 4. Fetch ranked recommendations from backend matching service
      let rankedData = [];
      try {
        rankedData = await matchingApi.getBestMatches(activeCv.id, 20);
      } catch (matchErr) {
        console.warn('Matching API error:', matchErr);
        rankedData = [];
      }

      // Handle backend response shape (List[MatchResponse] where each item has job_offer nested)
      const list = Array.isArray(rankedData) ? rankedData : (rankedData?.matches || []);
      const normalized = list.map(item => {
        if (item.match && item.job_offer) {
          return { match: item.match, job: item.job_offer };
        }
        const { job_offer, ...matchFields } = item;
        return { match: matchFields, job: job_offer || {} };
      }).filter(r => r.match && r.match.compatibility_score != null && r.job?.id);

      setRecs(normalized);

      // 4. SECONDARY: Fetch recent discoveries (unscored, compact)
      try {
        const queryKw = (prefs?.target_roles && prefs.target_roles.length > 0)
          ? prefs.target_roles.join(' ')
          : (prefs?.job_keywords || 'developer');

        const fresh = await jobsApi.searchJobs({
          keywords: queryKw,
          sort_by: 'newest',
          limit: 20,
        });

        const recJobIds = new Set(normalized.map(r => r.job.id));
        const unscored = (Array.isArray(fresh) ? fresh : []).filter(j =>
          j.compatibility_score == null && !recJobIds.has(j.id)
        );
        setDiscoveries(unscored.slice(0, 12));
      } catch (_) {}

    } catch (e) {
      console.error('Failed to load opportunities:', e);
      const detail = e.response?.data?.detail || e.message || 'Could not load your opportunities.';
      setError(`Failed to load opportunities: ${detail}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleTriggerSourcing = async () => {
    if (!cv?.id || triggeringSourcing) return;
    setTriggeringSourcing(true);
    try {
      await matchingApi.triggerSourcing(cv.id);
      setSourcingTriggered(true);
      setSourcingActive(true);
    } catch (e) {
      console.error('Trigger sourcing failed:', e);
    } finally {
      setTriggeringSourcing(false);
    }
  };

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  /* ── Search handler ──────────────────────────────────────── */
  const runSearch = useCallback(async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      const results = await jobsApi.searchJobs({
        keywords: searchQuery.trim(),
        location: location || undefined,
        contract_type: contract || undefined,
        sort_by: 'best_match',
        limit: 40,
      });
      setSearchResults(results);
    } catch (e) {
      setError('Search failed. Please try again.');
    } finally {
      setSearching(false);
    }
  }, [searchQuery, location, contract]);

  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults(null);
    setError('');
    inputRef.current?.focus();
  };

  /* ── Partition recommendations by category ───────────────── */
  const minThreshold = userPrefs?.min_match_score ?? 70;
  const exceptional = recommendations.filter(r => r.match.compatibility_score >= 90);
  const strong      = recommendations.filter(r => r.match.compatibility_score >= 80 && r.match.compatibility_score < 90);
  const good        = recommendations.filter(r => r.match.compatibility_score >= 70 && r.match.compatibility_score < 80);
  const potential   = recommendations.filter(r => r.match.compatibility_score < 70);

  const qualifyingMatches = recommendations.filter(r => r.match.compatibility_score >= minThreshold);
  const hasQualifyingMatches = qualifyingMatches.length > 0;

  /* ── Search results split ────────────────────────────────── */
  const searchScored   = searchResults ? searchResults.filter(j => j.compatibility_score != null) : [];
  const searchUnscored = searchResults ? searchResults.filter(j => j.compatibility_score == null) : [];

  /* ── Render ──────────────────────────────────────────────── */
  return (
    <CandidateShell>
      <div className="page disc-page">

        {/* ── HEADER ── */}
        <div className="disc-header disc-enter">
          <p className="eyebrow">
            <Target size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            AI Recruitment Agent
          </p>
          <h1 className="disc-title">Your Best Opportunities</h1>
          <p className="disc-subtitle">
            Your AI agent analyzed your CV, profile and preferences and ranked the most relevant opportunities for you.
          </p>
        </div>

        {/* ── SEARCH BAR ── */}
        <div className="disc-search-wrap disc-enter disc-enter--1">
          <form
            className="disc-search-form"
            onSubmit={e => { e.preventDefault(); runSearch(); }}
          >
            <div className="disc-search-input-wrap">
              <Search size={17} className="disc-search-icon" />
              <input
                ref={inputRef}
                className="disc-search-input"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Refine by role, company or technology…"
                aria-label="Search opportunities"
                spellCheck={false}
              />
              {searchQuery && (
                <button type="button" className="disc-search-clear" onClick={clearSearch} aria-label="Clear">
                  <X size={14} />
                </button>
              )}
            </div>

            <button
              type="button"
              className={`disc-filters-toggle ${filtersOpen ? 'active' : ''}`}
              onClick={() => setFiltersOpen(o => !o)}
              aria-label="Filters"
            >
              <SlidersHorizontal size={14} />
              {(location || contract) && <span className="disc-filters-badge" />}
            </button>

            <button type="submit" className="button primary disc-search-btn" disabled={searching}>
              {searching ? <RefreshCw size={14} className="disc-spin" /> : <Search size={14} />}
              {searching ? 'Searching…' : 'Search'}
            </button>
          </form>

          {filtersOpen && (
            <div className="disc-filters-panel disc-enter">
              <div className="disc-filter-group">
                <label className="disc-filter-label" htmlFor="f-loc"><MapPin size={11} /> Location</label>
                <input id="f-loc" className="input disc-filter-input" value={location}
                  onChange={e => setLocation(e.target.value)} placeholder="e.g. Paris, Remote…" />
              </div>
              <div className="disc-filter-group">
                <label className="disc-filter-label" htmlFor="f-ct"><Briefcase size={11} /> Contract</label>
                <select id="f-ct" className="select disc-filter-input" value={contract}
                  onChange={e => setContract(e.target.value)}>
                  <option value="">All types</option>
                  <option value="CDI">Permanent (CDI)</option>
                  <option value="CDD">Fixed-term (CDD)</option>
                  <option value="STAGE">Internship</option>
                  <option value="FREELANCE">Freelance</option>
                </select>
              </div>
              {(location || contract) && (
                <button type="button" className="disc-quiet-link" onClick={() => { setLocation(''); setContract(''); }}>
                  <X size={11} /> Clear filters
                </button>
              )}
            </div>
          )}
        </div>

        {/* ════════════════════════════════════════════════
            STATE: ERROR
        ════════════════════════════════════════════════ */}
        {error && !loading && (
          <div className="card" style={{ padding: '24px', background: '#fff1f2', border: '1.5px solid #fecdd3', borderRadius: '14px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#9f1239', fontWeight: 700, fontSize: '15px' }}>
              <AlertCircle size={20} />
              <span>{error}</span>
            </div>
            <div style={{ marginTop: '16px', display: 'flex', gap: '12px' }}>
              <button onClick={bootstrap} className="button primary" style={{ fontSize: '13px', padding: '8px 16px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <RotateCcw size={14} /> Retry Request
              </button>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════
            STATE: NO CV
        ════════════════════════════════════════════════ */}
        {!loading && cvLoaded && !cv && !error && (
          <div className="disc-state-card disc-enter">
            <div className="disc-state-icon disc-state-icon--warn">
              <FileText size={28} />
            </div>
            <div className="disc-state-body">
              <h2>Upload your CV to unlock personalized recommendations</h2>
              <p>
                Our AI recruitment agent will analyze your CV, extract your skills, experience and seniority,
                then rank the most compatible opportunities for you — automatically.
              </p>
              <Link href="/cv" className="button primary" style={{ marginTop: 16, display: 'inline-flex' }}>
                <FileText size={15} /> Upload CV
              </Link>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════
            STATE: CV PROCESSING
        ════════════════════════════════════════════════ */}
        {!loading && cv && cv.status !== 'PARSED' && !error && (
          <div className="disc-state-card disc-enter">
            <div className="disc-state-icon disc-state-icon--info">
              <Zap size={28} />
            </div>
            <div className="disc-state-body">
              <h2>Your AI profile is being prepared…</h2>
              <p>
                We're extracting your skills, experience and building your compatibility profile.
                Your ranked recommendations will appear here shortly.
              </p>
              <div className="disc-processing-bar">
                <div className="disc-processing-fill" />
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════
            STATE: LOADING
        ════════════════════════════════════════════════ */}
        {loading && <SkeletonFeed />}

        {/* ════════════════════════════════════════════════
            SEARCH RESULTS MODE
        ════════════════════════════════════════════════ */}
        {!loading && searchResults && (
          <div className="disc-feed disc-enter">
            <div className="disc-section-head" style={{ marginBottom: 8 }}>
              <h2 className="disc-section-title">
                <Search size={16} /> Results for "{searchQuery}"
              </h2>
              <button className="disc-quiet-link" onClick={clearSearch}>
                <X size={12} /> Back to recommendations
              </button>
            </div>

            {searchScored.length === 0 && searchUnscored.length === 0 && (
              <div className="disc-empty disc-enter">
                <Search size={26} />
                <h3>No results for "{searchQuery}"</h3>
                <p>Try different keywords or adjust your filters.</p>
              </div>
            )}

            {searchScored.length > 0 && (
              <div className="disc-category" style={{ marginBottom: 24 }}>
                <h3 className="disc-category-head">
                  <span><Sparkles size={14} /></span> Scored matches
                  <span className="disc-category-count">{searchScored.length}</span>
                </h3>
                <div className="disc-category-list">
                  {searchScored.map((job, i) => (
                    <RecommendationCard
                      key={job.id}
                      match={{ compatibility_score: job.compatibility_score, summary: job.summary, matching_points: [] }}
                      job={job}
                      idx={i}
                    />
                  ))}
                </div>
              </div>
            )}

            {searchUnscored.length > 0 && (
              <div className="disc-discoveries">
                <h3 className="disc-discoveries-head">
                  <Clock size={13} /> New discoveries from search
                  <span className="disc-category-count">{searchUnscored.length}</span>
                </h3>
                <div className="disc-discoveries-list">
                  {searchUnscored.map(job => <DiscoveryCard key={job.id} job={job} />)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════════
            PRIMARY FEED: AI RANKED RECOMMENDATIONS
        ════════════════════════════════════════════════ */}
        {!loading && !searchResults && cv?.status === 'PARSED' && !error && (
          <div className="disc-feed disc-enter">

            {/* AI agent status bar */}
            {/* AI agent status bar */}
            <div className="disc-agent-bar">
              <div className="disc-ai-dot" />
              <Sparkles size={12} />
              <span>
                {sourcingActive || sourcingTriggered ? (
                  <><strong>AI Agent Active</strong> · Searching external platforms for opportunities…</>
                ) : (relevantOffers === 0) ? (
                  <><strong>AI Agent Active</strong> · No relevant opportunities found · Sourcing required</>
                ) : !hasQualifyingMatches ? (
                  <><strong>AI Agent Active</strong> · {relevantOffers ?? totalOffers} relevant opportunities scanned · No qualifying matches</>
                ) : (
                  <><strong>AI Agent Active</strong> · {qualifyingMatches.length} qualified opportunities ranked · {discoveries.length} new discoveries</>
                )}
              </span>
            </div>

            {/* Zero qualifying results state machine */}
            {!hasQualifyingMatches && (
              <>
                {/* State 4: SOURCING IN PROGRESS */}
                {(sourcingActive || sourcingTriggered) && (
                  <div className="disc-empty disc-enter">
                    <RefreshCw size={28} className="disc-spin" style={{ color: 'var(--primary)' }} />
                    <h3>Searching for opportunities…</h3>
                    <p>
                      Our AI agent is actively searching multiple job platforms for roles matching your profile and preferences.
                      Opportunities will be evaluated and ranked as they are collected.
                    </p>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(59, 130, 246, 0.08)', color: '#2563eb', padding: '4px 12px', borderRadius: 999, fontSize: 12, fontWeight: 600, marginTop: 8 }}>
                      <Clock size={12} /> Background sourcing in progress
                    </div>
                  </div>
                )}

                {/* State 1: NO RELEVANT INVENTORY */}
                {!sourcingActive && !sourcingTriggered && (relevantOffers === 0) && (
                  <div className="disc-empty disc-enter">
                    <Target size={28} style={{ color: 'var(--primary)' }} />
                    <h3>Looking for opportunities matching your profile</h3>
                    <p>
                      We're looking for opportunities matching your profile. No relevant opportunities have been found yet in our inventory.
                      Our agent is monitoring available platforms to find roles tailored to your target criteria.
                    </p>
                    <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
                      <button
                        type="button"
                        className="button primary"
                        onClick={handleTriggerSourcing}
                        disabled={triggeringSourcing}
                        style={{ fontSize: 13 }}
                      >
                        {triggeringSourcing ? <RefreshCw size={14} className="disc-spin" /> : <Sparkles size={14} />}
                        {triggeringSourcing ? 'Starting search…' : 'Scan Platforms for Matches'}
                      </button>
                      <Link href="/settings" className="button secondary" style={{ fontSize: 13 }}>
                        Adjust Preferences
                      </Link>
                    </div>
                  </div>
                )}

                {/* State 2: RELEVANT JOBS EXIST, BUT NONE QUALIFY */}
                {!sourcingActive && !sourcingTriggered && (relevantOffers > 0) && (
                  <div className="disc-empty disc-enter" style={{ marginBottom: potential.length > 0 ? 24 : 0 }}>
                    <TrendingUp size={28} />
                    <h3>No strong matches yet</h3>
                    <p>
                      Opportunities were found in our inventory ({relevantOffers} relevant roles), but none currently meet your matching threshold ({minThreshold}%).
                      Try adjusting your preferences or target roles for broader results.
                    </p>
                    <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
                      <button
                        type="button"
                        className="button secondary"
                        onClick={handleTriggerSourcing}
                        disabled={triggeringSourcing}
                        style={{ fontSize: 13 }}
                      >
                        {triggeringSourcing ? <RefreshCw size={14} className="disc-spin" /> : <RefreshCw size={14} />}
                        Find More Offers
                      </button>
                      <Link href="/settings" className="button primary" style={{ fontSize: 13 }}>
                        Adjust Preferences
                      </Link>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* State 3: MATCHES AVAILABLE (Ranked categories) */}
            {hasQualifyingMatches && (
              <>
                <CategoryGroup
                  label="Exceptional Match" emoji="🥇"
                  items={exceptional}
                  renderItem={({ match, job }, i) => (
                    <RecommendationCard key={job.id} match={match} job={job} idx={i} userPrefs={userPrefs} />
                  )}
                />
                <CategoryGroup
                  label="Strong Match" emoji="🥈"
                  items={strong}
                  renderItem={({ match, job }, i) => (
                    <RecommendationCard key={job.id} match={match} job={job} idx={exceptional.length + i} userPrefs={userPrefs} />
                  )}
                />
                <CategoryGroup
                  label="Good Match" emoji="🥉"
                  items={good}
                  renderItem={({ match, job }, i) => (
                    <RecommendationCard key={job.id} match={match} job={job} idx={exceptional.length + strong.length + i} userPrefs={userPrefs} />
                  )}
                />
                <CategoryGroup
                  label="Potential Match" emoji="📋"
                  items={potential}
                  renderItem={({ match, job }, i) => (
                    <RecommendationCard key={job.id} match={match} job={job} idx={exceptional.length + strong.length + good.length + i} userPrefs={userPrefs} />
                  )}
                />
              </>
            )}

            {/* If there are potential matches below threshold when no qualifying match, display them */}
            {!hasQualifyingMatches && potential.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <CategoryGroup
                  label="Potential Opportunities (Below Threshold)" emoji="📋"
                  items={potential}
                  renderItem={({ match, job }, i) => (
                    <RecommendationCard key={job.id} match={match} job={job} idx={i} userPrefs={userPrefs} />
                  )}
                />
              </div>
            )}

            {/* SECONDARY: New discoveries (compact) */}
            {discoveries.length > 0 && (
              <div className="disc-discoveries disc-enter">
                <div className="disc-discoveries-head-row">
                  <h3 className="disc-discoveries-head">
                    <Clock size={13} /> New Discoveries
                    <span className="disc-category-count">{discoveries.length}</span>
                  </h3>
                  <p className="disc-discoveries-sub">
                    Recently found · No compatibility score yet
                  </p>
                </div>
                <div className="disc-discoveries-list">
                  {discoveries.map(job => <DiscoveryCard key={job.id} job={job} />)}
                </div>
              </div>
            )}

          </div>
        )}

      </div>
    </CandidateShell>
  );
}
