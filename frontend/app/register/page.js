'use client';

import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { User, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authApi } from '../../lib/api/auth';

/* ---- Icon components ---- */
function GoogleIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
  );
}

/* ---- Animated background SVG ---- */
function AuthVisualBg() {
  return (
    <svg
      className="auth-visual-bg"
      viewBox="0 0 600 800"
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle cx="500" cy="80"  r="300" fill="rgba(111,207,151,0.04)" />
      <circle cx="80"  cy="720" r="260" fill="rgba(111,207,151,0.04)" />
      <g stroke="rgba(111,207,151,0.13)" strokeWidth="1" fill="none">
        <line x1="80"  y1="190" x2="270" y2="310" strokeDasharray="220" style={{animation:'draw-line 3s ease 0.2s both'}} />
        <line x1="270" y1="310" x2="470" y2="210" strokeDasharray="220" style={{animation:'draw-line 3s ease 0.5s both'}} />
        <line x1="470" y1="210" x2="540" y2="420" strokeDasharray="220" style={{animation:'draw-line 3s ease 0.8s both'}} />
        <line x1="270" y1="310" x2="190" y2="490" strokeDasharray="220" style={{animation:'draw-line 3s ease 0.6s both'}} />
        <line x1="190" y1="490" x2="390" y2="570" strokeDasharray="220" style={{animation:'draw-line 3s ease 0.9s both'}} />
        <line x1="390" y1="570" x2="540" y2="420" strokeDasharray="220" style={{animation:'draw-line 3s ease 1.1s both'}} />
        <line x1="60"  y1="440" x2="190" y2="490" strokeDasharray="220" style={{animation:'draw-line 3s ease 0.7s both'}} />
        <line x1="390" y1="570" x2="310" y2="690" strokeDasharray="220" style={{animation:'draw-line 3s ease 1.3s both'}} />
      </g>
      <g fill="rgba(111,207,151,0.22)">
        <circle cx="80"  cy="190" r="5" style={{animation:'float-node 4.5s ease-in-out 0s   infinite'}} />
        <circle cx="270" cy="310" r="7" style={{animation:'float-node 4.5s ease-in-out 0.5s infinite'}} />
        <circle cx="470" cy="210" r="5" style={{animation:'float-node 4.5s ease-in-out 1s   infinite'}} />
        <circle cx="540" cy="420" r="4" style={{animation:'float-node 4.5s ease-in-out 1.5s infinite'}} />
        <circle cx="190" cy="490" r="6" style={{animation:'float-node 4.5s ease-in-out 0.8s infinite'}} />
        <circle cx="390" cy="570" r="5" style={{animation:'float-node 4.5s ease-in-out 1.2s infinite'}} />
        <circle cx="60"  cy="440" r="4" style={{animation:'float-node 4.5s ease-in-out 0.3s infinite'}} />
        <circle cx="310" cy="690" r="4" style={{animation:'float-node 4.5s ease-in-out 1.7s infinite'}} />
      </g>
      <circle cx="270" cy="310" r="22" stroke="rgba(111,207,151,0.12)" strokeWidth="1" fill="none" style={{animation:'pulse-ring 3.5s ease-in-out infinite'}} />
      <circle cx="270" cy="310" r="38" stroke="rgba(111,207,151,0.06)" strokeWidth="1" fill="none" style={{animation:'pulse-ring 3.5s ease-in-out 0.6s infinite'}} />
    </svg>
  );
}

/* ---- Password rules ---- */
const PW_RULES = [
  { key: 'length',  label: '8+ characters',        test: p => p.length >= 8 },
  { key: 'upper',   label: 'One uppercase letter',  test: p => /[A-Z]/.test(p) },
  { key: 'lower',   label: 'One lowercase letter',  test: p => /[a-z]/.test(p) },
  { key: 'digit',   label: 'One number',            test: p => /\d/.test(p) },
  { key: 'special', label: 'One special character', test: p => /[!@#$%^&*(),.?":{}|<>]/.test(p) },
];

/* ---- Main page ---- */
export default function RegisterPage() {
  const [fullName, setFullName]         = useState('');
  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [confirmPassword, setConfirm]   = useState('');
  const [showPassword, setShowPw]       = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);
  const [error, setError]               = useState('');
  const [success, setSuccess]           = useState(false);
  const [oauthLoading, setOAuthLoading] = useState('');
  const { register, loading } = useAuth();
  const router = useRouter();

  const emailRegex   = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const isEmailValid = emailRegex.test(email) || email === '';
  const pwRules      = PW_RULES.map(r => ({ ...r, met: r.test(password) }));
  const allMet       = pwRules.every(r => r.met);
  const pwMatch      = password === confirmPassword;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!fullName || !email || !password || !confirmPassword) { setError('Please fill in all fields.'); return; }
    if (!emailRegex.test(email)) { setError('Please enter a valid email address.'); return; }
    if (!allMet) { setError('Password does not meet all requirements.'); return; }
    if (!pwMatch) { setError('Passwords do not match.'); return; }

    const result = await register(email, password, fullName);
    if (result.success) {
      setSuccess(true);
      setTimeout(() => router.push('/login'), 1800);
    } else {
      setError(result.error || 'Registration failed. Please try again.');
    }
  };

  const handleOAuth = async (provider) => {
    setError('');
    setOAuthLoading(provider);
    try {
      const data = provider === 'google'
        ? await authApi.getGoogleAuthUrl()
        : await authApi.getGithubAuthUrl();
      window.location.href = data.authorization_url;
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || `${provider === 'google' ? 'Google' : 'GitHub'} login is not configured.`);
      setOAuthLoading('');
    }
  };

  const canSubmit = !loading && fullName && email && isEmailValid && allMet && pwMatch && confirmPassword;

  return (
    <div className="auth-split">

      {/* ── LEFT: visual panel ── */}
      <div className="auth-visual" aria-hidden="true">
        <AuthVisualBg />

        <div className="auth-visual-brand">
          <p className="auth-visual-brand-name"><b>n</b>ext<b>role</b></p>
          <p className="auth-visual-tagline">AI Recruitment Platform</p>
        </div>

        <div className="auth-visual-content">
          <h2 className="auth-visual-headline">
            Your career,<br /><em>upgraded by AI</em>
          </h2>
          <p className="auth-visual-desc">
            Join thousands of candidates who use nextrole to find better
            opportunities, apply smarter, and get more callbacks.
          </p>
          <div className="auth-visual-stats">
            <div className="auth-visual-stat">
              <strong>50k+</strong>
              <span>Active users</span>
            </div>
            <div className="auth-visual-stat">
              <strong>10k+</strong>
              <span>Jobs matched</span>
            </div>
            <div className="auth-visual-stat">
              <strong>Free</strong>
              <span>To get started</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── RIGHT: form panel ── */}
      <div className="auth-form-panel">
        <div className="auth-form-wrap">

          <span className="auth-form-logo">
            <b>n</b>ext<b style={{ color: 'var(--pine)' }}>role</b>
          </span>

          <h1 className="auth-heading">Create your account</h1>
          <p className="auth-sub">Get started — it&apos;s free</p>

          {error && (
            <div className="auth-error-banner" role="alert">
              <AlertCircle size={15} style={{ flex: 'none', marginTop: '2px' }} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="auth-success-banner" role="status">
              <CheckCircle2 size={15} style={{ flex: 'none', marginTop: '2px' }} />
              <span>Account created! Redirecting to login…</span>
            </div>
          )}

          {/* OAuth */}
          <div className="auth-oauth-group">
            <button
              type="button"
              className="auth-oauth-btn"
              onClick={() => handleOAuth('google')}
              disabled={!!oauthLoading}
              aria-label="Sign up with Google"
            >
              <GoogleIcon />
              {oauthLoading === 'google' ? 'Redirecting…' : 'Google'}
            </button>
            <button
              type="button"
              className="auth-oauth-btn"
              onClick={() => handleOAuth('github')}
              disabled={!!oauthLoading}
              aria-label="Sign up with GitHub"
            >
              <GitHubIcon />
              {oauthLoading === 'github' ? 'Redirecting…' : 'GitHub'}
            </button>
          </div>

          <div className="auth-divider">
            <div className="auth-divider-line" />
            <span className="auth-divider-text">or email</span>
            <div className="auth-divider-line" />
          </div>

          {/* Registration form */}
          <form onSubmit={handleSubmit} noValidate>

            {/* Full name */}
            <div className="field">
              <label htmlFor="reg-name">Full name</label>
              <div className="auth-input-wrap">
                <span className="auth-input-icon"><User size={15} /></span>
                <input
                  id="reg-name"
                  type="text"
                  className="input input-with-icon"
                  placeholder="Jane Smith"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  autoComplete="name"
                  required
                />
              </div>
            </div>

            {/* Email */}
            <div className="field">
              <label htmlFor="reg-email">Email address</label>
              <div className="auth-input-wrap">
                <span className="auth-input-icon"><Mail size={15} /></span>
                <input
                  id="reg-email"
                  type="email"
                  className="input input-with-icon"
                  placeholder="you@email.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  style={{ borderColor: email && !isEmailValid ? 'var(--danger)' : undefined }}
                />
              </div>
              {email && !isEmailValid && (
                <p className="auth-input-error">Please enter a valid email address</p>
              )}
            </div>

            {/* Password */}
            <div className="field">
              <label htmlFor="reg-password">Password</label>
              <div className="auth-input-wrap">
                <span className="auth-input-icon"><Lock size={15} /></span>
                <input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  className="input input-with-icon input-with-action"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  className="auth-input-action"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>

              {/* Progressive password rules — only shown when typing */}
              {password && (
                <div className="auth-pw-rules" role="list" aria-label="Password requirements">
                  {pwRules.map(r => (
                    <div
                      key={r.key}
                      className={`auth-pw-rule ${r.met ? 'met' : 'unmet'}`}
                      role="listitem"
                      aria-label={`${r.label}: ${r.met ? 'satisfied' : 'not satisfied'}`}
                    >
                      <span className="auth-pw-rule-dot" />
                      {r.label}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div className="field">
              <label htmlFor="reg-confirm">Confirm password</label>
              <div className="auth-input-wrap">
                <span className="auth-input-icon"><Lock size={15} /></span>
                <input
                  id="reg-confirm"
                  type={showConfirm ? 'text' : 'password'}
                  className="input input-with-icon input-with-action"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={e => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  required
                  style={{ borderColor: confirmPassword && !pwMatch ? 'var(--danger)' : undefined }}
                />
                <button
                  type="button"
                  className="auth-input-action"
                  onClick={() => setShowConfirm(v => !v)}
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {confirmPassword && !pwMatch && (
                <p className="auth-input-error">Passwords do not match</p>
              )}
            </div>

            <button
              type="submit"
              className="button primary auth-submit"
              disabled={!canSubmit}
            >
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="auth-footer-text">
            Already have an account?{' '}
            <Link href="/login">Sign in</Link>
          </p>

        </div>
      </div>
    </div>
  );
}
