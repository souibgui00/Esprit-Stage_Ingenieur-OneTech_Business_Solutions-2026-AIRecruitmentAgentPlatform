'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Lock, Eye, EyeOff, CheckCircle, AlertCircle, ArrowLeft } from 'lucide-react';
import { authApi } from '../../../lib/api/auth';

function ResetPasswordForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const token        = searchParams.get('token');

  const [password, setPassword]         = useState('');
  const [confirmPassword, setConfirm]   = useState('');
  const [showPassword, setShowPw]       = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);
  const [loading, setLoading]           = useState(false);
  const [success, setSuccess]           = useState(false);
  const [error, setError]               = useState('');

  // Password strength rules (must match backend)
  const rules = {
    length:    password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    digit:     /\d/.test(password),
    special:   /[!@#$%^&*(),.?":{}|<>]/.test(password),
  };
  const allRulesMet    = Object.values(rules).every(Boolean);
  const passwordsMatch = password === confirmPassword;

  useEffect(() => {
    if (!token) {
      setError('Invalid or missing reset token. Please request a new reset link.');
    }
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!token) { setError('Missing reset token.'); return; }
    if (!allRulesMet) { setError('Password does not meet the requirements below.'); return; }
    if (!passwordsMatch) { setError('Passwords do not match.'); return; }

    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err) {
      const msg = err.response?.data?.detail || 'The reset link is invalid or has expired. Please request a new one.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div style={{ textAlign: 'center' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '50%',
              background: '#f0fdf4', display: 'grid', placeItems: 'center',
              margin: '0 auto 1.25rem'
            }}>
              <CheckCircle size={32} style={{ color: '#22c55e' }} />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: '750', letterSpacing: '-0.03em', margin: '0 0 8px', color: 'var(--ink)' }}>
              Password updated!
            </h1>
            <p style={{ color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6', margin: '0 0 1.5rem' }}>
              Your password has been changed successfully. Redirecting you to login…
            </p>
            <Link href="/login" className="button primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
              Sign in now
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '24px', fontWeight: '750', letterSpacing: '-0.04em', margin: '0 0 8px', color: 'var(--ink)' }}>
            Set a new password
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: '14px', margin: 0 }}>
            Choose a strong password for your account.
          </p>
        </div>

        {error && (
          <div style={{
            background: '#fff1f1', border: '1px solid #f0c2c2', color: 'var(--danger)',
            padding: '12px 16px', borderRadius: '8px', fontSize: '14px',
            marginBottom: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '8px'
          }}>
            <AlertCircle size={16} style={{ flex: 'none', marginTop: '2px' }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* New password */}
          <div className="field">
            <label htmlFor="password" style={{ fontSize: '13px', fontWeight: '650', marginBottom: '6px', display: 'block' }}>
              New password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                className="input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoFocus
                style={{ paddingLeft: '40px', paddingRight: '40px' }}
              />
              <button type="button" onClick={() => setShowPw(!showPassword)}
                style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', padding: '4px', cursor: 'pointer', color: 'var(--muted)', display: 'flex' }}>
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Strength checklist */}
            {password && (
              <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {[
                  [rules.length,    '8+ characters'],
                  [rules.uppercase, 'One uppercase letter (A-Z)'],
                  [rules.lowercase, 'One lowercase letter (a-z)'],
                  [rules.digit,     'One number (0-9)'],
                  [rules.special,   'One special character (!@#…)'],
                ].map(([met, label]) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: met ? '#22c55e' : 'var(--muted)' }}>
                    <span style={{ fontSize: '10px' }}>{met ? '✓' : '○'}</span>
                    {label}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Confirm password */}
          <div className="field" style={{ marginTop: '1rem' }}>
            <label htmlFor="confirm" style={{ fontSize: '13px', fontWeight: '650', marginBottom: '6px', display: 'block' }}>
              Confirm new password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
              <input
                type={showConfirm ? 'text' : 'password'}
                id="confirm"
                className="input"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirm(e.target.value)}
                required
                style={{ paddingLeft: '40px', paddingRight: '40px', borderColor: confirmPassword && !passwordsMatch ? 'var(--danger)' : undefined }}
              />
              <button type="button" onClick={() => setShowConfirm(!showConfirm)}
                style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', padding: '4px', cursor: 'pointer', color: 'var(--muted)', display: 'flex' }}>
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {confirmPassword && !passwordsMatch && (
              <p style={{ color: 'var(--danger)', fontSize: '13px', margin: '4px 0 0' }}>Passwords do not match</p>
            )}
          </div>

          <button
            type="submit"
            className="button primary"
            style={{ width: '100%', marginTop: '1.5rem', padding: '12px 16px', fontSize: '15px' }}
            disabled={loading || !token || !allRulesMet || !passwordsMatch || !password || !confirmPassword}
          >
            {loading ? 'Updating…' : 'Set new password'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '14px' }}>
          <Link href="/login" style={{ color: 'var(--pine)', fontWeight: '500', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={14} /> Back to Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="auth-page"><div className="auth-card">Loading…</div></div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
