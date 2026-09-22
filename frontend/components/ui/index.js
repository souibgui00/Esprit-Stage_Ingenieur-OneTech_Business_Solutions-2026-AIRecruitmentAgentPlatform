import { AlertCircle, Briefcase, MapPin, Sparkles, Clock } from 'lucide-react';
import Link from 'next/link';

export function Button({ children, variant = 'primary', className = '', ...props }) {
  return (
    <button className={`button ${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Card({ children, className = '' }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Badge({ children, tone = '' }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}

export function EmptyState({ title, message, action }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{message}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div className="error">
      <AlertCircle size={16} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
      {message}
    </div>
  );
}

export function LoadingState({ label = 'Loading your workspace…' }) {
  return (
    <div className="empty">
      <p>{label}</p>
    </div>
  );
}

export function getMatchLabel(score) {
  if (score === null || score === undefined) return null;
  const val = Math.round(score);
  if (val >= 85) return 'Exceptional Match';
  if (val >= 75) return 'Strong Match';
  if (val >= 60) return 'Good Match';
  if (val >= 45) return 'Moderate Match';
  return 'Potential Match';
}

export function MatchScore({ score, showLabel = true }) {
  if (score === null || score === undefined) {
    return (
      <div className="match-badge match-pending" title="Match evaluation pending">
        <Clock size={11} />
        <span className="match-tag">Match pending</span>
      </div>
    );
  }
  const val = Math.round(score);
  const label = getMatchLabel(val);
  const toneClass = val >= 75 ? 'match-high' : val >= 50 ? 'match-mid' : 'match-low';

  return (
    <div className={`match-badge ${toneClass}`} title={`${val}% Match - ${label}`}>
      <span className="match-num">{val}%</span>
      {showLabel && <span className="match-tag">{label}</span>}
    </div>
  );
}

export function StatusBadge({ status }) {
  const labels = {
    DRAFT: 'Draft',
    PENDING_VALIDATION: 'Ready to review',
    APPROVED: 'Approved',
    SUBMITTING: 'Submitting',
    SENT: 'Applied',
    FAILED: 'Failed',
    ACTION_REQUIRED: 'Action required',
    MANUAL_REQUIRED: 'Action required',
    REJECTED: 'Not pursuing',
  };
  
  const tones = {
    DRAFT: 'muted',
    PENDING_VALIDATION: 'info',
    APPROVED: 'success',
    SUBMITTING: 'warning',
    SENT: 'success',
    FAILED: 'error',
    ACTION_REQUIRED: 'warning',
    MANUAL_REQUIRED: 'warning',
    REJECTED: 'muted',
  };
  
  return <Badge tone={tones[status] || ''}>{labels[status] || status}</Badge>;
}

export function JobCard({ job, match, href }) {
  const score = match?.compatibility_score ?? job.compatibility_score;
  const summary = match?.summary || job.summary;

  return (
    <Link href={href || `/jobs/${job.id}`} className="card job-card">
      <div className="job-top">
        <div>
          <h3 className="job-title">{job.title}</h3>
          <p className="company">{job.company}</p>
        </div>
        <MatchScore score={score} />
      </div>
      <div className="job-meta">
        <span>
          <MapPin size={14} /> {job.location || 'Location not specified'}
        </span>
        <span>
          <Briefcase size={14} /> {job.contract_type || 'Opportunity'}
        </span>
      </div>

      {summary && (
        <p className="job-card-summary">
          <Sparkles size={12} className="summary-sparkle" /> {summary}
        </p>
      )}

      <div className="job-bottom">
        <span className="quiet">View detailed analysis →</span>
      </div>
    </Link>
  );
}
