/**
 * LoginPage — Minimal authentication gate.
 * Supports email/password sign-in and sign-up.
 */
import { useState } from 'react';
import { Lock, Mail, Eye, EyeOff, AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useI18n } from '../hooks/useI18n';

export default function LoginPage() {
  const { signIn, signUp } = useAuth();
  const { lang, setLang, t } = useI18n();
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
        setError(t('login_err_invalid'));
      } else if (code === 'auth/email-already-in-use') {
        setError(t('login_err_exists'));
      } else if (code === 'auth/weak-password') {
        setError(t('login_err_weak'));
      } else if (code === 'auth/invalid-email') {
        setError(t('login_err_email'));
      } else {
        setError(err.message || t('login_err_generic'));
      }
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-page flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Language toggle — lightweight, top-right */}
        <div className="flex justify-end mb-4 gap-1">
          <button
            onClick={() => setLang('en')}
            className={`px-2 py-1 rounded text-xs font-semibold transition-colors cursor-pointer ${
              lang === 'en' ? 'bg-brand-light text-brand-dark' : 'text-text-placeholder hover:bg-hover'
            }`}
          >EN</button>
          <button
            onClick={() => setLang('zh-CN')}
            className={`px-2 py-1 rounded text-xs font-semibold transition-colors cursor-pointer ${
              lang === 'zh-CN' ? 'bg-brand-light text-brand-dark' : 'text-text-placeholder hover:bg-hover'
            }`}
          >中文</button>
        </div>

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white text-lg font-extrabold mx-auto mb-4 shadow-lg">
            Q
          </div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">{t('login_brand')}</h1>
          <p className="text-sm text-text-placeholder mt-1">{t('login_tagline')}</p>
        </div>

        {/* Form */}
        <div className="bg-card rounded-2xl border border-border shadow-card p-8">
          <h2 className="text-lg font-bold text-text-primary mb-1">
            {isSignUp ? t('login_create') : t('login_signin')}
          </h2>
          <p className="text-sm text-text-placeholder mb-6">
            {isSignUp ? t('login_create_sub') : t('login_signin_sub')}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('login_email')}</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-placeholder" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder={t('login_email_ph')}
                  required
                  className="w-full h-11 pl-10 pr-4 bg-border-light border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('login_password')}</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-placeholder" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="w-full h-11 pl-10 pr-10 bg-border-light border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-placeholder hover:text-text-secondary"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full h-11 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.3)] hover:brightness-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  {isSignUp ? t('login_create') : t('login_signin')}
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => { setIsSignUp(!isSignUp); setError(''); }}
              className="text-sm text-brand hover:text-brand-dark font-medium transition-colors"
            >
              {isSignUp ? t('login_has_account') : t('login_no_account')}
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-text-placeholder mt-6">
          {t('login_footer')}
        </p>
      </div>
    </div>
  );
}
