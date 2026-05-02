import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ScreeningRunCreate } from '@/lib/types'

export function useScreeningRuns(projectId: string) {
  return useQuery({
    queryKey: ['screeningRuns', projectId],
    queryFn: () => api.screening.runs(projectId),
    enabled: !!projectId,
    refetchInterval: (query) => {
      const data = query.state.data
      const hasActive = data?.some(
        (r) => r.status === 'running' || r.status === 'pending',
      )
      return hasActive ? 3000 : false
    },
  })
}

export function useStartScreening(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ScreeningRunCreate) => api.screening.start(projectId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] }),
  })
}

export function useCancelScreening(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => api.screening.cancel(projectId, runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] }),
  })
}
