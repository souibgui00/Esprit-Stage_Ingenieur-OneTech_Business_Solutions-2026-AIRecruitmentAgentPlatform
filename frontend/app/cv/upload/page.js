'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import CandidateShell from '../../../components/layout/CandidateShell';
import { cvApi } from '../../../lib/api/cv';
import {
  UploadCloud, FileText, ArrowLeft, CheckCircle2, AlertCircle, Sparkles, RefreshCw
} from 'lucide-react';

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');

  const validateAndSetFile = (selectedFile) => {
    if (!selectedFile) return;
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Please choose a valid PDF file (.pdf).');
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError('The PDF file must be 10 MB or smaller.');
      return;
    }
    setFile(selectedFile);
    setError('');
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    setStatusMessage('Uploading PDF and extracting skills & experience…');

    try {
      const cv = await cvApi.upload(file);
      setStatusMessage('✓ CV successfully processed! Redirecting to profile…');
      setTimeout(() => {
        router.push('/cv');
      }, 1000);
    } catch (err) {
      console.error('CV upload error:', err);
      const detail = err.response?.data?.detail || 'We could not analyze this PDF file. Please ensure it is a valid, text-based PDF.';
      setError(detail);
      setStatusMessage('');
      setUploading(false);
    }
  };

  return (
    <CandidateShell>
      <div className="page" style={{ maxWidth: '720px' }}>

        {/* Back Link */}
        <div style={{ marginBottom: '24px' }}>
          <Link href="/cv" className="disc-quiet-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={15} /> Back to My CV
          </Link>
        </div>

        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <p className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <UploadCloud size={12} /> CV Upload & Analysis
          </p>
          <h1 style={{ fontSize: 'clamp(26px, 4vw, 36px)', fontWeight: 800, letterSpacing: '-0.04em', margin: '0 0 10px', color: 'var(--ink)' }}>
            Upload or Replace CV
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: '15px', margin: 0 }}>
            Upload your PDF resume. Our AI agent will extract your skills, experience, and update your compatibility match scores.
          </p>
        </div>

        {/* Notice Card */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          background: 'var(--mint)', border: '1px solid #b6dcc2',
          borderRadius: '12px', padding: '16px 20px', marginBottom: '24px'
        }}>
          <Sparkles size={18} style={{ color: 'var(--pine)', flexShrink: 0 }} />
          <div style={{ fontSize: '13.5px', color: 'var(--pine-dark)', lineHeight: 1.4 }}>
            <strong>Single CV Policy:</strong> Uploading a new CV replaces your current active CV and automatically recalculates match recommendations.
          </div>
        </div>

        {/* Upload Box */}
        <div className="card" style={{ padding: '32px', textAlign: 'center' }}>

          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${dragActive ? 'var(--pine)' : 'var(--line)'}`,
              background: dragActive ? 'var(--mint)' : 'var(--soft)',
              borderRadius: '16px', padding: '40px 24px',
              transition: 'all 0.2s ease', cursor: 'pointer',
              marginBottom: '24px'
            }}
            onClick={() => document.getElementById('cv-file-input').click()}
          >
            <input
              id="cv-file-input"
              type="file"
              accept="application/pdf,.pdf"
              onChange={e => validateAndSetFile(e.target.files[0])}
              style={{ display: 'none' }}
            />

            <div style={{
              width: '56px', height: '56px', borderRadius: '50%', background: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
            }}>
              <UploadCloud size={26} style={{ color: 'var(--pine)' }} />
            </div>

            {file ? (
              <div>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#fff', padding: '8px 16px', borderRadius: '999px', border: '1px solid var(--line)' }}>
                  <FileText size={16} style={{ color: 'var(--pine)' }} />
                  <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--ink)' }}>{file.name}</span>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>({(file.size / (1024 * 1024)).toFixed(2)} MB)</span>
                </div>
                <p style={{ fontSize: '12.5px', color: 'var(--pine)', fontWeight: 600, marginTop: '10px' }}>
                  Click to select a different file
                </p>
              </div>
            ) : (
              <div>
                <p style={{ fontWeight: 800, fontSize: '16px', margin: '0 0 6px', color: 'var(--ink)' }}>
                  Drag & drop your CV here, or <span style={{ color: 'var(--pine)', textDecoration: 'underline' }}>browse</span>
                </p>
                <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>
                  Supports text-based PDF files up to 10 MB.
                </p>
              </div>
            )}
          </div>

          {error && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              background: '#fff1f2', border: '1px solid #fecdd3',
              borderRadius: '10px', padding: '12px 16px',
              color: '#9f1239', fontWeight: 600, fontSize: '13.5px', marginBottom: '20px',
              textAlign: 'left'
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              {error}
            </div>
          )}

          {statusMessage && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              background: '#f0fdf4', border: '1px solid #bbf7d0',
              borderRadius: '10px', padding: '12px 16px',
              color: '#166534', fontWeight: 600, fontSize: '13.5px', marginBottom: '20px',
              textAlign: 'left'
            }}>
              <RefreshCw size={15} className="disc-spin" style={{ flexShrink: 0 }} />
              {statusMessage}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <Link href="/cv" className="button secondary" style={{ fontSize: '14px' }}>
              Cancel
            </Link>
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="button primary"
              style={{ padding: '10px 24px', fontSize: '14.5px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            >
              {uploading ? <RefreshCw size={15} className="disc-spin" /> : <UploadCloud size={15} />}
              {uploading ? 'Analyzing PDF…' : 'Upload & Analyze CV'}
            </button>
          </div>

        </div>

      </div>
    </CandidateShell>
  );
}
