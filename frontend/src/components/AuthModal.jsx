import React, { useState } from 'react';
import { X, Lock, Mail, User, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../services/api';

export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isRegister) {
        await api.register(username, email, password);
        // Auto-login after registration
        const authData = await api.login(username, password);
        onAuthSuccess(authData.user);
      } else {
        const authData = await api.login(username, password);
        onAuthSuccess(authData.user);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1.5rem',
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '420px',
        background: 'rgba(15, 23, 42, 0.95)',
        padding: '2rem',
        boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
      }}>
        {/* Top Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: '700' }}>
            {isRegister ? 'Create Account' : 'Welcome Back'}
          </h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {error && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#f87171',
            padding: '8px 12px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            marginBottom: '1rem',
          }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Username / Identifier */}
          <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '0 12px' }}>
            <User size={18} color="#64748b" />
            <input
              type="text"
              placeholder={isRegister ? "Username" : "Username or Email"}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{ width: '100%', background: 'transparent', border: 'none', color: '#fff', padding: '10px', fontSize: '0.9rem', outline: 'none' }}
            />
          </div>

          {/* Email (only for registration) */}
          {isRegister && (
            <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '0 12px' }}>
              <Mail size={18} color="#64748b" />
              <input
                type="email"
                placeholder="Email Address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ width: '100%', background: 'transparent', border: 'none', color: '#fff', padding: '10px', fontSize: '0.9rem', outline: 'none' }}
              />
            </div>
          )}

          {/* Password */}
          <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '0 12px' }}>
            <Lock size={18} color="#64748b" />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{ width: '100%', background: 'transparent', border: 'none', color: '#fff', padding: '10px', fontSize: '0.9rem', outline: 'none' }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="gradient-btn"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '0.5rem', padding: '10px' }}
          >
            {loading && <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />}
            <span>{isRegister ? 'Register & Sign In' : 'Sign In'}</span>
          </button>
        </form>

        {/* Toggle between Login and Register */}
        <div style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.85rem', color: '#94a3b8' }}>
          {isRegister ? (
            <span>Already have an account? <button onClick={() => { setIsRegister(false); setError(null); }} style={{ background: 'transparent', border: 'none', color: 'var(--accent-primary)', fontWeight: '600', cursor: 'pointer' }}>Sign In</button></span>
          ) : (
            <span>Don't have an account? <button onClick={() => { setIsRegister(true); setError(null); }} style={{ background: 'transparent', border: 'none', color: 'var(--accent-primary)', fontWeight: '600', cursor: 'pointer' }}>Register</button></span>
          )}
        </div>
      </div>
    </div>
  );
}
