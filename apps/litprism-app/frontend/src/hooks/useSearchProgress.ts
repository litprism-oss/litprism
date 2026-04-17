import { useEffect, useRef, useState } from 'react'

export interface SearchProgressEvent {
  event: 'search_progress' | 'search_complete' | 'search_error'
  source?: string
  fetched?: number
  total?: number
  total_articles?: number
  duplicates_removed?: number
  message?: string
}

export function useSearchProgress(projectId: string | null) {
  const [events, setEvents] = useState<SearchProgressEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!projectId) return
    const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
    const ws = new WebSocket(`${WS_URL}/ws/${projectId}`)
    wsRef.current = ws
    ws.onopen = () => setIsConnected(true)
    ws.onclose = () => setIsConnected(false)
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data) as SearchProgressEvent
      setEvents((prev) => [...prev, data])
    }
    return () => {
      ws.close()
      setIsConnected(false)
    }
  }, [projectId])

  const clearEvents = () => setEvents([])
  return { events, isConnected, clearEvents }
}
