import { useQueryClient } from '@tanstack/react-query'
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { useState } from 'react'
import { ApiError, postGoogleLogin } from '../api/client'
import { Logo } from './Logo'

export function Login() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onCredential(response: CredentialResponse) {
    setError(null)
    if (!response.credential) {
      setError('No credential returned by Google — please try again.')
      return
    }
    setBusy(true)
    try {
      await postGoogleLogin(response.credential)
      await queryClient.invalidateQueries({ queryKey: ['me'] }) // flips the gate into the app
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError("This account isn't authorized — contact your admin.")
      } else {
        setError('Sign-in failed — please try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative flex h-full items-center justify-center overflow-hidden bg-app p-6">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-1/4 left-1/2 h-[560px] w-[560px] -translate-x-1/2 rounded-full opacity-80 blur-3xl"
        style={{ background: 'radial-gradient(circle, var(--brand-soft), transparent 65%)' }}
      />
      <div className="card elevate-pop relative w-full max-w-sm rounded-2xl p-8">
        <div className="flex flex-col items-center text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-soft text-brand ring-1 ring-brand/20">
            <Logo size={30} />
          </span>
          <h1 className="mt-4 text-[20px] font-semibold tracking-tight text-fg">AuthorityScout</h1>
          <p className="mt-1.5 text-[13px] text-fg-muted">
            Sign in to access your outreach prospects.
          </p>
        </div>

        <div className={`mt-7 flex justify-center ${busy ? 'pointer-events-none opacity-60' : ''}`}>
          <GoogleLogin
            onSuccess={onCredential}
            onError={() => setError('Sign-in failed — please try again.')}
            theme="filled_black"
            shape="pill"
            size="large"
            text="signin_with"
            width="280"
          />
        </div>

        {error && (
          <div className="mt-4 rounded-md bg-rose-500/10 px-3 py-2 text-center text-[12px] text-rose-600 dark:text-rose-400">
            {error}
          </div>
        )}

        <p className="mt-6 text-center text-[11px] text-fg-subtle">
          Private tool — access is limited to authorized team members.
        </p>
      </div>
    </div>
  )
}
