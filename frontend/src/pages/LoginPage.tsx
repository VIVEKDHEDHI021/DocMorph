import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { FileText, Lock, Mail, ArrowRight, Sparkles, AlertCircle, Loader2 } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [devLoading, setDevLoading] = useState(false);

  const { login, initializeAnonymousSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleDevLogin = async () => {
    setError(null);
    setDevLoading(true);
    try {
      await initializeAnonymousSession();
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Failed to initialize session.');
    } finally {
      setDevLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 shadow-lg shadow-indigo-200">
            <FileText className="h-8 w-8 text-white" />
          </div>
          <h2 className="mt-6 text-3xl font-extrabold tracking-tight text-slate-900">
            Welcome back to DocMorph
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Personalize your academic lab reports and practicals with confidence.
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-100">
          {/* Quick Dev Demo Access */}
          <div className="mb-6 rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-600" />
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-900">
                  Instant Preview
                </span>
              </div>
              <span className="rounded-full bg-indigo-200/60 px-2 py-0.5 text-xs font-medium text-indigo-800">
                1-Click Access
              </span>
            </div>
            <p className="mt-1 text-xs text-indigo-700">
              Test full upload, detection & replacement without creating a new password.
            </p>
            <button
              type="button"
              onClick={handleDevLogin}
              disabled={devLoading || loading}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60"
            >
              {devLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Logging in guest demo...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Quick Dev Demo Guest Sign-In
                </>
              )}
            </button>
          </div>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-3 font-medium text-slate-500">Or sign in with email</span>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-5 flex items-center gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3.5 text-sm text-rose-700">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                Email address
              </label>
              <div className="relative mt-1.5">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <Mail className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="student@docmorph.dev"
                  className="block w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Password
                </label>
              </div>
              <div className="relative mt-1.5">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <Lock className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••••••"
                  className="block w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || devLoading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2 disabled:opacity-60"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Footer note */}
          <div className="mt-6 text-center text-sm text-slate-600">
            Don't have an account yet?{' '}
            <Link to="/signup" className="font-semibold text-indigo-600 hover:text-indigo-500">
              Sign up free
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

