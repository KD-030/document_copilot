import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

function signInErrorMessage(error: unknown): string {
  if (
    error instanceof Error &&
    (error.name === 'AuthRetryableFetchError' ||
      /failed to fetch|networkerror/i.test(error.message))
  ) {
    return `Could not reach Supabase Auth at ${env.supabaseUrl}. Check VITE_SUPABASE_URL and your network, then restart the frontend.`
  }
  return error instanceof Error ? error.message : 'Unable to sign in.'
}

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      })

      if (signInError) {
        setError(signInErrorMessage(signInError))
        return
      }
      navigate('/', { replace: true })
    } catch (signInError) {
      setError(signInErrorMessage(signInError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 px-4 py-10">
      <section className="w-full max-w-sm rounded-xl border bg-card p-7 shadow-sm">
        <div className="mb-7">
          <p className="text-sm font-semibold text-primary">DRIFTWOOD CAPITAL</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Document Copilot
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sign in with your analyst account to search SEC filings.
          </p>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block space-y-2 text-sm font-medium" htmlFor="email">
            Email
            <input
              autoComplete="email"
              className="h-10 w-full rounded-md border bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
              id="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label
            className="block space-y-2 text-sm font-medium"
            htmlFor="password"
          >
            Password
            <input
              autoComplete="current-password"
              className="h-10 w-full rounded-md border bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
              id="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <Button className="w-full" disabled={isSubmitting} type="submit">
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
          Accounts are managed by your administrator. Sign-up is not available
          from this page.
        </p>
      </section>
    </main>
  )
}
