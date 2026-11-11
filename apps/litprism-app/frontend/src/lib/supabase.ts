import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

/** Null when the Supabase variables are not set: the app then runs without a login
 *  screen (local development with AUTH_DISABLED=true on the backend). */
export const supabase: SupabaseClient | null = url && anonKey ? createClient(url, anonKey) : null

export const authEnabled = supabase !== null

/** The signed-in user's access token, or null when logged out or auth is off. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}
