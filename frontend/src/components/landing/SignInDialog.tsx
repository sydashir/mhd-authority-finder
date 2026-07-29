import { AlertCircle, Eye, EyeOff, Loader2, Lock, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, postLogin } from '../../api/client'
import { Logo } from '../Logo'

/**
 * The sign-in dialog. Username and password only: no third-party account, no email
 * handed to anyone. On success we invalidate ['me'], which flips the auth gate in
 * App.tsx and drops the user straight into the workspace.
 */
export function SignInDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [reveal, setReveal] = useState(false)
  const usernameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    // Focus the first field so the dialog is usable from the keyboard immediately.
    const id = window.setTimeout(() => usernameRef.current?.focus(), 40)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(id)
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  if (!open) return null

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (busy) return
    // Read the DOM, not React state: browsers autofill credentials without firing onChange,
    // which would otherwise submit an empty password against a form that looks filled in.
    const data = new FormData(e.currentTarget)
    const submittedUser = String(data.get('username') ?? '').trim()
    const submittedPass = String(data.get('password') ?? '')
    setBusy(true)
    setError(null)
    try {
      await postLogin(submittedUser, submittedPass)
      setPassword('')
      await queryClient.invalidateQueries({ queryKey: ['me'] })
    } catch (err) {
      // The API returns one message for a bad username OR password, and a distinct
      // 429 when the client is locked out. Show whichever it sent.
      setError(
        err instanceof ApiError
          ? err.message
          : 'Could not reach the server. Is the backend running?',
      )
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="signin-title"
    >
      <button
        type="button"
        aria-label="Close sign in"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-app/80 backdrop-blur-sm"
      />
      <div className="card elevate-pop relative w-full max-w-[380px] p-7 duration-200 animate-in">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 rounded-md p-1.5 text-fg-subtle transition-colors hover:bg-raised hover:text-fg"
        >
          <X size={16} />
        </button>

        <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
          <Logo size={24} />
        </span>
        <h2 id="signin-title" className="mt-4 text-[19px] font-semibold tracking-tight text-fg">
          Sign in to AuthorityScout
        </h2>
        <p className="mt-1 text-[13px] text-fg-muted">Your workspace credentials.</p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <label htmlFor="username" className="block text-[12px] font-medium text-fg-muted">
              Username
            </label>
            <input
              id="username"
              name="username"
              ref={usernameRef}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              className="w-full rounded-lg border border-border bg-app px-3 py-2 text-[13px] text-fg transition-colors placeholder:text-fg-subtle/70 hover:border-border-strong focus:border-brand focus:outline-none"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="block text-[12px] font-medium text-fg-muted">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                name="password"
                type={reveal ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="w-full rounded-lg border border-border bg-app py-2 pl-3 pr-10 text-[13px] text-fg transition-colors hover:border-border-strong focus:border-brand focus:outline-none"
              />
              {/* Reveal, so a wrong value autofilled by the browser is visible rather than
                  hidden behind dots while the sign-in keeps failing. */}
              <button
                type="button"
                onClick={() => setReveal((r) => !r)}
                aria-label={reveal ? 'Hide password' : 'Show password'}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-fg-subtle transition-colors hover:bg-raised hover:text-fg"
              >
                {reveal ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {error && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-lg px-3 py-2 text-[12px] leading-snug"
              style={{ background: 'var(--flag-bg)', color: 'var(--flag-fg)' }}
            >
              <AlertCircle size={14} className="mt-px shrink-0" />
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-[13px] font-semibold text-brand-fg transition-all hover:bg-brand-strong active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Lock size={14} />}
            {busy ? 'Signing in' : 'Sign in'}
          </button>
        </form>

        <p className="mt-5 border-t border-border pt-4 text-[11.5px] leading-relaxed text-fg-subtle">
          Private tool for the District Behavioral Health outreach team. Accounts are created by
          your admin.
        </p>
      </div>
    </div>
  )
}
