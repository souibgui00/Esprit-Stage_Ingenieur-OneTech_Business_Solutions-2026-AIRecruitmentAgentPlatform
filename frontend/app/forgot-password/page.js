'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Mail, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';
import { authApi } from '../../lib/api/auth';

export default function ForgotPasswordPage() {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent]       = useState(false);
  const [error, setError]     = useState('');

  const emailRegex  = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const isEmailValid = emailRegex.test(email) || email === '';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address.');
      return;
    }

    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (err) {
      // Always show the same message to prevent user enumeration
      setSent(true);
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '50%',
              background: '#f0fdf4', display: 'grid', placeItems: 'center',
              margin: '0 auto 1.25rem'
            }}>
              <CheckCircle size={32} style={{ color: '#22c55e' }} />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: '750', letterSpacing: '-0.03em', margin: '0 0 8px', color: 'var(--ink)' }}>
              Check your inbox
            </h1>
            <p style={{ color: 'var(--muted)', fontSize: '14px', lineHeight: '1.6', margin: 0 }}>
              If <strong>{email}</strong> is registered, a password reset link has been sent.
              The link expires in <strong>1 hour</strong>.
            </p>
          </div>

          <div style={{
            background: 'var(--soft)', borderRadius: '8px',
            padding: '14px 16px', fontSize: '13px', color: 'var(--muted)',
            marginBottom: '1.5rem', lineHeight: '1.6'
          }}>
            Didn't receive it? Check your spam folder, or{' '}
            <button
              onClick={() => { setSent(false); setEmail(''); }}
              style={{ background: 'none', border: 'none', color: 'var(--pine)', fontWeight: '600', cursor: 'pointer', fontSize: '13px', padding: 0 }}
            >
              try a different email
            </button>.
          </div>

          <Link href="/login" className="button secondary" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <ArrowLeft size={16} /> Back to Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '24px', fontWeight: '750', letterSpacing: '-0.04em', margin: '0 0 8px', color: 'var(--ink)' }}>
            Reset your password
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: '14px', margin: 0 }}>
            Enter your email and we'll send you a reset link.
          </p>
        </div>

        {error && (
          <div style={{
            background: '#fff1f1', border: '1px solid #f0c2c2',
            color: 'var(--danger)', padding: '12px 16px', borderRadius: '8px',
            fontSize: '14px', marginBottom: '1.5rem',
            display: 'flex', alignItems: 'center', gap: '8px'
          }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email" style={{ fontSize: '13px', fontWeight: '650', marginBottom: '6px', display: 'block' }}>
              Email address
            </label>
            <div style={{ position: 'relative' }}>
              <Mail size={16} style={{
                position: 'absolute', left: '12px', top: '50%',
                transform: 'translateY(-50%)', color: 'var(--muted)'
              }} />
              <input
                type="email"
                id="email"
                className="input"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                style={{ paddingLeft: '40px', borderColor: email && !isEmailValid ? 'var(--danger)' : undefined }}
              />
            </div>
            {email && !isEmailValid && (
              <p style={{ color: 'var(--danger)', fontSize: '13px', margin: '4px 0 0' }}>
                Please enter a valid email address
              </p>
            )}
          </div>

          <button
            type="submit"
            className="button primary"
            style={{ width: '100%', marginTop: '1.5rem', padding: '12px 16px', fontSize: '15px' }}
            disabled={loading || !email || !isEmailValid}
          >
            {loading ? 'Sending…' : 'Send reset link'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '14px', color: 'var(--muted)' }}>
          <Link href="/login" style={{ color: 'var(--pine)', fontWeight: '500', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={14} /> Back to Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}