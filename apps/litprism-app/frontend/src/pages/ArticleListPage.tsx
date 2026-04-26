import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useSearchRuns } from '@/hooks/useSearchRuns'
import { useUploads } from '@/hooks/useUpload'
import { useArticles } from '@/hooks/useArticles'
import { ArticleRow } from '@/components/articles/ArticleRow'
import { ArticleQualityBanner } from '@/components/articles/ArticleQualityBanner'
import { formatDate, formatCount } from '@/lib/utils'

const SOURCE_LABELS: Record<string, string> = {
  pubmed:          'PubMed',
  europepmc:       'Europe PMC',
  semanticscholar: 'Semantic Scholar',
}

const PAGE_SIZE = 50

export function ArticleListPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')

  const sourceQueryId = searchParams.get('source_query_id') ?? undefined
  const uploadRecordId = searchParams.get('upload_record_id') ?? undefined

  const { data: searchRuns } = useSearchRuns(projectId ?? '')
  const { data: uploads } = useUploads(projectId ?? '')
  const { data, isLoading } = useArticles(projectId ?? '', {
    source_query_id: sourceQueryId,
    upload_record_id: uploadRecordId,
    page,
    page_size: PAGE_SIZE,
  })

  const sourceQuery = sourceQueryId
    ? searchRuns?.flatMap((r) => r.source_queries).find((sq) => sq.id === sourceQueryId)
    : undefined

  const uploadRecord = uploadRecordId
    ? uploads?.find((u) => u.id === uploadRecordId)
    : undefined

  const filteredItems = query
    ? (data?.items ?? []).filter(
        (a) =>
          a.title.toLowerCase().includes(query.toLowerCase()) ||
          (a.abstract ?? '').toLowerCase().includes(query.toLowerCase()),
      )
    : (data?.items ?? [])

  const total = data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  let pageTitle = 'Articles'
  let pageMeta = ''
  let queryDisplay = ''

  if (sourceQuery) {
    const label = SOURCE_LABELS[sourceQuery.source] ?? sourceQuery.source
    pageTitle = `${label} · ${formatCount(sourceQuery.result_count)} articles`
    pageMeta = `Searched ${formatDate(sourceQuery.searched_at)}`
    queryDisplay = sourceQuery.query_string
  } else if (uploadRecord) {
    pageTitle = `${uploadRecord.filename} · ${formatCount(uploadRecord.record_count)} records`
    pageMeta = `Uploaded ${formatDate(uploadRecord.uploaded_at)}`
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 800, margin: '0 auto' }}>
      <div style={{ marginBottom: 16 }}>
        <p style={{
          fontSize: 15,
          fontWeight: 500,
          color: 'var(--color-text-primary)',
          marginBottom: 4,
        }}>
          {pageTitle}
        </p>

        {pageMeta && (
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{pageMeta}</p>
        )}

        {queryDisplay && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 4 }}>
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--color-text-secondary)',
              flex: 1,
              wordBreak: 'break-all',
            }}>
              {queryDisplay}
            </p>
            <button
              onClick={() => navigator.clipboard.writeText(queryDisplay)}
              style={{
                fontSize: 11,
                background: 'none',
                border: '0.5px solid var(--color-border-tertiary)',
                padding: '2px 8px',
                borderRadius: 'var(--border-radius-md)',
                cursor: 'pointer',
                color: 'var(--color-text-secondary)',
                flexShrink: 0,
              }}
            >
              Copy
            </button>
          </div>
        )}
      </div>

      {uploadRecord && data?.items && data.items.length > 0 && (
        <ArticleQualityBanner filename={uploadRecord.filename} articles={data.items} />
      )}

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
        gap: 12,
      }}>
        <input
          type="text"
          placeholder="Search within results…"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setPage(1) }}
          style={{
            flex: 1,
            fontSize: 12,
            padding: '6px 10px',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-md)',
            background: 'var(--color-background-primary)',
            color: 'var(--color-text-primary)',
            outline: 'none',
          }}
        />
        {total > 0 && (
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', flexShrink: 0 }}>
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {formatCount(total)}
          </span>
        )}
      </div>

      {isLoading ? (
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', paddingTop: 24 }}>
          Loading…
        </p>
      ) : filteredItems.length === 0 ? (
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', paddingTop: 24 }}>
          {query ? 'No articles match your search.' : 'No articles found.'}
        </p>
      ) : (
        filteredItems.map((article) => <ArticleRow key={article.id} article={article} />)
      )}

      {pageCount > 1 && !query && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: 16,
          fontSize: 13,
          color: 'var(--color-text-secondary)',
        }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              fontSize: 13,
              background: 'none',
              border: '0.5px solid var(--color-border-tertiary)',
              padding: '5px 12px',
              borderRadius: 'var(--border-radius-md)',
              cursor: page === 1 ? 'default' : 'pointer',
              color: page === 1 ? 'var(--color-text-tertiary)' : 'var(--color-text-secondary)',
            }}
          >
            ← Prev
          </button>
          <span>Page {page} of {pageCount} · {formatCount(total)} articles</span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            disabled={page === pageCount}
            style={{
              fontSize: 13,
              background: 'none',
              border: '0.5px solid var(--color-border-tertiary)',
              padding: '5px 12px',
              borderRadius: 'var(--border-radius-md)',
              cursor: page === pageCount ? 'default' : 'pointer',
              color: page === pageCount ? 'var(--color-text-tertiary)' : 'var(--color-text-secondary)',
            }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
