import { useState } from 'react'
import { supabase } from '@/lib/supabase'

type Mode = 'signin' | 'signup'

const field: React.CSSProperties = {
  width: '100%',
  minHeight: 44,
  padding: '0 12px',
  fontSize: 14,
  fontFamily: 'inherit',
  color: 'var(--color-text-primary)',
  background: 'var(--color-background-primary)',
  border: '0.5px solid var(--color-border-secondary)',
  borderRadius: 'var(--border-radius-md)',
}

const primary: React.CSSProperties = {
  width: '100%',
  minHeight: 44,
  fontSize: 14,
  fontWeight: 500,
  fontFamily: 'inherit',
  color: 'var(--color-background-primary)',
  background: 'var(--color-text-primary)',
  border: 'none',
  borderRadius: 'var(--border-radius-md)',
  cursor: 'pointer',
}

export function LoginPage() {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  if (!supabase) return null
  const client = supabase

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    const result =
      mode === 'signin'
        ? await client.auth.signInWithPassword({ email, password })
        : await client.auth.signUp({
            email,
            password,
            options: { emailRedirectTo: window.location.origin },
          })
    setBusy(false)
    if (result.error) {
      setError(result.error.message)
    } else if (mode === 'signup' && !result.data.session) {
      setNotice('Check your email to confirm your account, then sign in.')
    }
    // On success the AuthGate sees the new session and shows the app.
  }

  async function magicLink() {
    if (!email) {
      setError('Enter your email first.')
      return
    }
    setBusy(true)
    setError(null)
    const { error: err } = await client.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    })
    setBusy(false)
    if (err) setError(err.message)
    else setNotice('We emailed you a sign-in link.')
  }

  return (
    <div
      style={{
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        background: 'var(--color-background-tertiary)',
      }}
    >
      <form
        onSubmit={submit}
        style={{
          width: '100%',
          maxWidth: 380,
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-lg)',
          padding: 24,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div>
          <p style={{ fontSize: 18, fontWeight: 500 }}>LitPrism</p>
          <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginTop: 2 }}>
            {mode === 'signin' ? 'Sign in to your reviews' : 'Create an account'}
          </p>
        </div>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={field}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
          Password
          <input
            type="password"
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={field}
          />
        </label>

        {error && (
          <p role="alert" style={{ fontSize: 13, color: '#791F1F' }}>
            {error}
          </p>
        )}
        {notice && (
          <p role="status" style={{ fontSize: 13, color: '#27500A' }}>
            {notice}
          </p>
        )}

        <button type="submit" disabled={busy} style={{ ...primary, opacity: busy ? 0.6 : 1 }}>
          {mode === 'signin' ? 'Sign in' : 'Create account'}
        </button>
        <button
          type="button"
          onClick={magicLink}
          disabled={busy}
          style={{
            ...primary,
            color: 'var(--color-text-primary)',
            background: 'var(--color-background-primary)',
            border: '0.5px solid var(--color-border-secondary)',
            fontWeight: 400,
          }}
        >
          Email me a sign-in link
        </button>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'signin' ? 'signup' : 'signin')
            setError(null)
            setNotice(null)
          }}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 13,
            fontFamily: 'inherit',
            color: 'var(--color-text-secondary)',
            cursor: 'pointer',
            minHeight: 36,
          }}
        >
          {mode === 'signin' ? 'New here? Create an account' : 'Have an account? Sign in'}
        </button>
      </form>
    </div>
  )
}
