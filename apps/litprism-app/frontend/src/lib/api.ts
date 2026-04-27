import type {
  ProjectOut,
  ProjectCreate,
  ProjectUpdate,
  SearchRunOut,
  SearchRunCreate,
  SearchRunUpdate,
  SearchPreviewRequest,
  SearchPreviewResponse,
  ArticleListOut,
  ArticleWithResultListOut,
  UploadRecordOut,
  UploadResponseOut,
  PRISMAFlowCounts,
  CriteriaOut,
  ScreeningRunOut,
  ScreeningRunCreate,
  ScreeningPreviewResult,
  ScreeningResultOut,
  ScreeningDecision,
} from '@/lib/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((error as { detail?: string }).detail ?? 'Request failed')
  }
  return res.json() as Promise<T>
}

export const api = {
  projects: {
    list: () => request<ProjectOut[]>('/projects'),
    get: (id: string) => request<ProjectOut>(`/projects/${id}`),
    create: (body: ProjectCreate) =>
      request<ProjectOut>('/projects', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: ProjectUpdate) =>
      request<ProjectOut>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    delete: (id: string) =>
      request<void>(`/projects/${id}`, { method: 'DELETE' }),
  },
  searchRuns: {
    list: (projectId: string) =>
      request<SearchRunOut[]>(`/projects/${projectId}/search-runs`),
    get: (projectId: string, runId: string) =>
      request<SearchRunOut>(`/projects/${projectId}/search-runs/${runId}`),
    create: (projectId: string, body: SearchRunCreate) =>
      request<SearchRunOut>(`/projects/${projectId}/search-runs`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    update: (projectId: string, runId: string, body: SearchRunUpdate) =>
      request<SearchRunOut>(`/projects/${projectId}/search-runs/${runId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    execute: (projectId: string, runId: string) =>
      request<SearchRunOut>(`/projects/${projectId}/search-runs/${runId}/execute`, {
        method: 'POST',
      }),
    preview: (projectId: string, body: SearchPreviewRequest) =>
      request<SearchPreviewResponse>(`/projects/${projectId}/search-runs/preview`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    articles: (projectId: string, runId: string, page = 1, pageSize = 50) =>
      request<ArticleListOut>(
        `/projects/${projectId}/search-runs/${runId}/articles?page=${page}&page_size=${pageSize}`,
      ),
  },
  upload: {
    upload: (projectId: string, formData: FormData) =>
      request<UploadResponseOut>(`/projects/${projectId}/upload`, {
        method: 'POST',
        body: formData,
        headers: {},
      }),
    list: (projectId: string) =>
      request<UploadRecordOut[]>(`/projects/${projectId}/uploads`),
  },
  articles: {
    list: (
      projectId: string,
      params?: {
        source_query_id?: string
        upload_record_id?: string
        page?: number
        page_size?: number
      },
    ) => {
      const qs = new URLSearchParams()
      if (params?.source_query_id) qs.set('source_query_id', params.source_query_id)
      if (params?.upload_record_id) qs.set('upload_record_id', params.upload_record_id)
      if (params?.page) qs.set('page', String(params.page))
      if (params?.page_size) qs.set('page_size', String(params.page_size))
      return request<ArticleListOut>(
        `/projects/${projectId}/articles${qs.toString() ? '?' + qs : ''}`,
      )
    },
  },
  prisma: {
    counts: (projectId: string) =>
      request<PRISMAFlowCounts>(`/projects/${projectId}/prisma-counts`),
  },
  criteria: {
    get: (projectId: string) =>
      request<CriteriaOut>(`/projects/${projectId}/criteria`),
    history: (projectId: string) =>
      request<CriteriaOut[]>(`/projects/${projectId}/criteria/history`),
    create: (projectId: string, body: { inclusion: string[]; exclusion: string[] }) =>
      request<CriteriaOut>(`/projects/${projectId}/criteria`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },
  screening: {
    start: (projectId: string, body: ScreeningRunCreate) =>
      request<ScreeningRunOut>(`/projects/${projectId}/screening/run`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    runs: (projectId: string) =>
      request<ScreeningRunOut[]>(`/projects/${projectId}/screening/runs`),
    get: (projectId: string, runId: string) =>
      request<ScreeningRunOut>(`/projects/${projectId}/screening/runs/${runId}`),
    resume: (projectId: string, runId: string) =>
      request<ScreeningRunOut>(`/projects/${projectId}/screening/runs/${runId}/resume`, {
        method: 'POST',
      }),
    cancel: (projectId: string, runId: string) =>
      request<ScreeningRunOut>(`/projects/${projectId}/screening/runs/${runId}/cancel`, { method: 'POST' }),
    preview: (
      projectId: string,
      body: { criteria: { inclusion: string[]; exclusion: string[] }; articles: { id: string; title: string; abstract: string | null }[] },
    ) =>
      request<ScreeningPreviewResult[]>(`/projects/${projectId}/screening/preview`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },
  screeningResults: {
    list: (
      projectId: string,
      params?: { decision?: ScreeningDecision; page?: number; page_size?: number },
    ) => {
      const qs = new URLSearchParams()
      if (params?.decision) qs.set('decision', params.decision)
      if (params?.page) qs.set('page', String(params.page))
      if (params?.page_size) qs.set('page_size', String(params.page_size))
      return request<ArticleWithResultListOut>(
        `/projects/${projectId}/screening/results${qs.toString() ? '?' + qs : ''}`,
      )
    },
    override: (
      projectId: string,
      articleId: string,
      body: { decision: ScreeningDecision; note?: string },
    ) =>
      request<ScreeningResultOut>(
        `/projects/${projectId}/screening/${articleId}/override`,
        { method: 'POST', body: JSON.stringify(body) },
      ),
  },
  export_: {
    download: (projectId: string, format: string) =>
      fetch(`${BASE_URL}/projects/${projectId}/export/${format}`).then(r => r.blob()),
  },
}
