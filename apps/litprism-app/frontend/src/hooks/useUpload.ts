import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useUploadFile(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (formData: FormData) => api.upload.upload(projectId, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uploads', projectId] })
      qc.invalidateQueries({ queryKey: ['projects', projectId] })
    },
  })
}

export function useUploads(projectId: string) {
  return useQuery({
    queryKey: ['uploads', projectId],
    queryFn: () => api.upload.list(projectId),
    enabled: !!projectId,
  })
}
