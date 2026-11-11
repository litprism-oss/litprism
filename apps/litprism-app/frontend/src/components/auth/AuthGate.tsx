import { useEffect, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { useQueryClient } from '@tanstack/react-query'
import { LoginPage } from '@/pages/LoginPage'
import { supabase } from '@/lib/supabase'

/** Shows the login screen until there is a session. Without Supabase variables
 *  (local dev) it renders the app directly. */
export function AuthGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(supabase !== null)

  useEffect(() => {
    if (!supabase) return
    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
      // Never show one account's cached data to the next.
      if (!next) queryClient.clear()
    })
    return () => data.subscription.unsubscribe()
  }, [queryClient])

  if (!supabase) return <>{children}</>
  if (loading) return null
  if (!session) return <LoginPage />
  return <>{children}</>
}
