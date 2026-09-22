'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { authApi } from '../lib/api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    async function loadUser() {
      if (typeof window === 'undefined') {
        setLoading(false);
        return;
      }

      const token = localStorage.getItem('token');
      if (token) {
        try {
          const userData = await authApi.getMe();
          setUser(userData);
        } catch (error) {
          console.error('Failed to load user:', error);
          localStorage.removeItem('token');
          localStorage.removeItem('refresh_token');
          setUser(null);
        }
      }
      setLoading(false);
    }
    loadUser();
  }, []);

  useEffect(() => {
    if (loading) return;

    const publicRoutes = [
      '/login',
      '/register',
      '/forgot-password',
      '/auth/reset-password',
      '/auth/google/callback',
      '/auth/github/callback',
    ];
    const isPublicRoute = publicRoutes.includes(pathname);

    if (!user && !isPublicRoute) {
      router.push('/login');
      return;
    }

    if (user && isPublicRoute) {
      router.push('/');
      return;
    }
  }, [user, loading, pathname, router]);

  const login = async (email, password) => {
    try {
      const data = await authApi.login(email, password);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      
      const userData = await authApi.getMe();
      setUser(userData);
      
      router.push('/');
      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map(e => e.msg || String(e)).join('. ')
        : (detail || error.message || 'Login failed');
      return { success: false, error: message };
    }
  };

  const register = async (email, password, full_name) => {
    try {
      await authApi.register(email, password, full_name);
      return { success: true };
    } catch (error) {
      const detail = error.response?.data?.detail;
      // FastAPI 422 validation errors return detail as an array of objects
      const message = Array.isArray(detail)
        ? detail.map(e => e.msg || String(e)).join('. ')
        : (detail || 'Registration failed');
      return { success: false, error: message };
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      router.push('/login');
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
