/**
 * LoginPage — Minimal authentication gate.
 * Supports email/password sign-in and sign-up.
 */
import { useState } from 'react';
import { Lock, Mail, Eye, EyeOff, AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError('');
    try {
      if (isSignUp) {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
    } catch (err) {
      const code = err.code || '';
      if (code === 'auth/user-not-found' || code === 'auth/wrong-password' || code === 'auth/invalid-credential') {
        setError('Invalid email or password');
      } else if (code === 'auth/email-already-in-use') {
        setError('Account already exists. Please sign in.');
      } else if (code === 'auth/weak-password') {
        setError('Password must be at least 6 characters');
      } else if (code === 'auth/invalid-email') {
        setError('Invalid email address');
      } else {
        setError(err.message || 'Authentication failed');
      }
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#67C23A] to-[#529b2e] flex items-center justify-center text-white text-lg font-extrabold mx-auto mb-4 shadow-lg">
            Q
          </div>
          <h1 className="text-2xl font-bold text-[#1A1A2E] tracking-tight">QuantCore Platform</h1>
          <p className="text-sm text-[#909399] mt-1">Quantitative Research & Controlled Execution</p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-2xl border border-[#EBEEF5] shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-8">
          <h2 className="text-lg font-bold text-[#1A1A2E] mb-1">
            {isSignUp ? 'Create Account' : 'Sign In'}
          </h2>
          <p className="text-sm text-[#909399] mb-6">
            {isSignUp ? 'Set up your research workspace' : 'Access your research workspace'}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-[#909399] mb-1.5 block">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#909399]" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full h-11 pl-10 pr-4 bg-[#F2F6FC] border border-[#EBEEF5] rounded-lg text-sm text-[#1A1A2E] placeholder-[#C0C4CC] focus:border-[#67C23A] focus:ring-2 focus:ring-[#67C23A]/20 outline-none transition-all"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-[#909399] mb-1.5 block">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#909399]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="w-full h-11 pl-10 pr-10 bg-[#F2F6FC] border border-[#EBEEF5] rounded-lg text-sm text-[#1A1A2E] placeholder-[#C0C4CC] focus:border-[#67C23A] focus:ring-2 focus:ring-[#67C23A]/20 outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#909399] hover:text-[#606266]"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full h-11 bg-gradient-to-r from-[#67C23A] to-[#529b2e] text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.3)] hover:brightness-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  {isSignUp ? 'Create Account' : 'Sign In'}
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => { setIsSignUp(!isSignUp); setError(''); }}
              className="text-sm text-[#67C23A] hover:text-[#529b2e] font-medium transition-colors"
            >
              {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-[#C0C4CC] mt-6">
          Controlled research platform — live trading disabled by default
        </p>
      </div>
    </div>
  );
}
