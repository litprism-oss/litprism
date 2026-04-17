import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { SearchRunCreate, SearchRunUpdate, SearchPreviewRequest } from '@/lib/types'

export function useSearchRuns(projectId: string) {
  return useQuery({
    queryKey: ['searchRuns', projectId],
    queryFn: () => api.searchRuns.list(projectId),
    enabled: !!projectId,
  })
}

export function useSearchRun(projectId: string, runId: string) {
  return useQuery({
    queryKey: ['searchRuns', projectId, runId],
    queryFn: () => api.searchRuns.get(projectId, runId),
    enabled: !!projectId && !!runId,
  })
}

export function useCreateSearchRun(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SearchRunCreate) => api.searchRuns.create(projectId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['searchRuns', projectId] }),
  })
}

export function useUpdateSearchRun(projectId: string, runId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SearchRunUpdate) => api.searchRuns.update(projectId, runId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['searchRuns', projectId] }),
  })
}

export function useExecuteSearch(projectId: string, runId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.searchRuns.execute(projectId, runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['searchRuns', projectId] }),
  })
}

export function useSearchPreview(projectId: string) {
  return useMutation({
    mutationFn: (body: SearchPreviewRequest) => api.searchRuns.preview(projectId, body),
  })
}
