import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ScreeningDecision } from '@/lib/types'

export function useScreeningResults(
  projectId: string,
  params?: { run_id?: string; decision?: ScreeningDecision; page?: number; page_size?: number },
) {
  return useQuery({
    queryKey: ['screeningResults', projectId, params],
    queryFn: () => api.screeningResults.list(projectId, params),
    enabled: !!projectId,
  })
}

export function useOverrideDecision(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      articleId,
      decision,
      note,
    }: {
      articleId: string
      decision: ScreeningDecision
      note?: string
    }) => api.screeningResults.override(projectId, articleId, { decision, note }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screeningResults', projectId] }),
  })
}
