import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useCriteria(projectId: string) {
  return useQuery({
    queryKey: ['criteria', projectId],
    queryFn: () => api.criteria.get(projectId),
    enabled: !!projectId,
  })
}

export function useCriteriaHistory(projectId: string) {
  return useQuery({
    queryKey: ['criteria', projectId, 'history'],
    queryFn: () => api.criteria.history(projectId),
    enabled: !!projectId,
  })
}

export function useCreateCriteria(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { inclusion: string[]; exclusion: string[] }) =>
      api.criteria.create(projectId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['criteria', projectId] })
      qc.invalidateQueries({ queryKey: ['projects', projectId] })
    },
  })
}
