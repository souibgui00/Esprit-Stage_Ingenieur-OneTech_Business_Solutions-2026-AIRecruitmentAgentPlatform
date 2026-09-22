'use client';

import { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi } from '../../../../lib/api/auth';

function GoogleCallbackHandler() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState('');
  const codeHandledRef   = useRef(false);

  useEffect(() => {
    const code     = searchParams.get('code');
    const errParam = searchParams.get('error');

    if (errParam) {
      setError(`Google denied access: ${errParam}`);
      return;
    }

    if (!code) {
      setError('No authorization code received from Google.');
      return;
    }

    // Prevent double execution in React StrictMode
    if (codeHandledRef.current) return;
    codeHandledRef.current = true;

    authApi.exchangeGoogleCode(code)
      .then((data) => {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        // Hard navigate to force AuthContext to re-read localStorage
        window.location.href = '/';
      })
      .catch((err) => {
        const detail = err.response?.data?.detail || err.message || 'Google login failed.';
        setError(detail);
      });
  }, [searchParams]);

  if (error) {
    return (
      <div className="auth-page">
        <div className="auth-card" style={{ textAlign: 'center' }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '50%',
            background: '#fff1f1', display: 'grid', placeItems: 'center',
            margin: '0 auto 1.25rem'
          }}>
            <span style={{ fontSize: '24px' }}>⚠️</span>
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 8px', color: 'var(--ink)' }}>
            Google Login Failed
          </h1>
          <p style={{ color: 'var(--danger)', fontSize: '14px', margin: '0 0 1.5rem', lineHeight: '1.6' }}>
            {error}
          </p>
          <button
            onClick={() => window.location.href = '/login'}
            className="button secondary"
            style={{ width: '100%' }}
          >
            ← Back to Sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <div style={{
          width: '56px', height: '56px', borderRadius: '50%',
          background: '#f0fdf4', display: 'grid', placeItems: 'center',
          margin: '0 auto 1.25rem'
        }}>
          <span style={{ fontSize: '24px' }}>🔄</span>
        </div>
        <h1 style={{ fontSize: '18px', fontWeight: '650', margin: '0 0 6px', color: 'var(--ink)' }}>
          Signing you in with Google…
        </h1>
        <p style={{ color: 'var(--muted)', fontSize: '14px', margin: 0 }}>
          Please wait a moment.
        </p>
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={
      <div className="auth-page">
        <div className="auth-card" style={{ textAlign: 'center' }}>
          <p style={{ color: 'var(--muted)' }}>Loading…</p>
        </div>
      </div>
    }>
      <GoogleCallbackHandler />
    </Suspense>
  );
}
