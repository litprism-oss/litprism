export type ReviewType =
  | 'systematic'
  | 'scoping'
  | 'rapid'
  | 'literature'
  | 'state_of_art'

export interface ProjectOut {
  id: string
  name: string
  description: string | null
  research_question: string | null
  review_type: ReviewType
  created_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  research_question?: string
  review_type: ReviewType
}

export interface ProjectUpdate {
  name?: string
  description?: string
  research_question?: string
}

export interface SourceQueryOut {
  id: string
  source: string
  interface: string
  query_string: string
  filters_applied: Record<string, unknown>
  filters_human_readable: string
  searched_at: string
  result_count: number
}

export interface SearchRunOut {
  id: string
  project_id: string
  review_type: ReviewType
  query_natural: string | null
  query_generated: string | null
  query_final: string | null
  filters: Record<string, unknown> | null
  sources: string[]
  status: 'draft' | 'locked' | 'completed' | 'failed'
  locked_at: string | null
  completed_at: string | null
  created_at: string
  source_queries: SourceQueryOut[]
}

export interface SearchRunCreate {
  review_type: string
  query_natural?: string
  filters?: Record<string, unknown>
  sources?: string[]
}

export interface SearchRunUpdate {
  query_natural?: string
  query_final?: string
  // query_generated — add when PICO-to-query generation is implemented (Session 10)
  filters?: Record<string, unknown>
  sources?: string[]
}

export interface SearchPreviewRequest {
  query_final: string
  filters?: Record<string, unknown>
  sources?: string[]
}

export interface SearchPreviewSource {
  source: string
  estimated_count: number
  sample_titles: string[]
  error: string | null
}

export interface SearchPreviewResponse {
  total_estimated: number
  sources: SearchPreviewSource[]
  query_translations: Record<string, string>
}

export interface ArticleOut {
  id: string
  pmid: string | null
  doi: string | null
  source: string
  upload_format: string | null
  title: string
  abstract: string | null
  authors: Array<{ last_name: string; fore_name?: string | null }>
  journal: string | null
  pub_date: string | null
  publication_year: number | null
  created_at: string
}

export interface ArticleListOut {
  items: ArticleOut[]
  total: number
  page: number
  page_size: number
}

export interface ArticleQualitySummary {
  total: number
  has_title: number
  has_abstract: number
  has_authors: number
  has_doi: number
}

export interface UploadRecordOut {
  id: string
  filename: string
  format: string
  uploaded_at: string
  record_count: number
  source_label: string | null
  search_strategy_used: string | null
  limits_applied: string | null
}

export interface UploadResponseOut {
  upload_id: string
  filename: string
  format: string
  total_parsed: number
  new_articles: number
  duplicates_found: number
  project_id: string
}

export interface PRISMAFlowCounts {
  db_records: number
  other_records: number
  duplicates_removed: number
  records_screened: number
  excluded_screening: number
  uncertain: number
  fulltext_assessed: number | null
  fulltext_excluded: number | null
  studies_included: number
}
