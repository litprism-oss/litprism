import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useArticles(
  projectId: string,
  params?: {
    source_query_id?: string
    upload_record_id?: string
    page?: number
    page_size?: number
  },
) {
  return useQuery({
    queryKey: ['articles', projectId, params],
    queryFn: () => api.articles.list(projectId, params),
    enabled: !!projectId,
  })
}
