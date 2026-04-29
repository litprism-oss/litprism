import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ArticleOut } from '@/lib/types'

function qualityColour(count: number, total: number): string {
  if (total === 0) return '#27500A'
  const pct = count / total
  if (pct > 0.9) return '#27500A'
  if (pct >= 0.5) return '#633806'
  return '#791F1F'
}

function qualityIcon(count: number, total: number): string {
  if (total === 0) return '✅'
  const pct = count / total
  if (pct > 0.9) return '✅'
  if (pct >= 0.5) return '⚠'
  return '✗'
}

interface ArticleQualityBannerProps {
  filename: string
  articles: ArticleOut[]
  projectId: string
  uploadRecordId?: string
}

export function ArticleQualityBanner({
  filename,
  articles,
  projectId,
  uploadRecordId,
}: ArticleQualityBannerProps) {
  const { data: enrichment } = useQuery({
    queryKey: ['enrichment', projectId, uploadRecordId],
    queryFn: () => api.enrichment.status(projectId, uploadRecordId),
    refetchInterval: (query) =>
      (query.state.data?.pending ?? 0) > 0 ? 5000 : false,
    enabled: !!uploadRecordId,
  })

  // Use server-side totals when available (full upload), fall back to current page
  const total = enrichment?.total ?? articles.length
  const enrichableTotal = enrichment ? enrichment.total - enrichment.skipped : null

  // Server-side quality counts (full upload); fall back to current page counts
  const hasTitleCount  = enrichment?.has_title   ?? articles.filter((a) => a.title?.trim()).length
  const hasDoiCount    = enrichment?.has_doi      ?? articles.filter((a) => a.doi?.trim()).length
  const hasAuthorsCount = enrichment?.has_authors ?? articles.filter((a) => a.authors?.length > 0).length

  const fields: Array<{ label: string; param: string; count: number }> = [
    { label: 'title',   param: 'title',   count: hasTitleCount },
    { label: 'authors', param: 'authors', count: hasAuthorsCount },
    { label: 'DOI',     param: 'doi',     count: hasDoiCount },
  ]

  return (
    <div style={{
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 'var(--border-radius-md)',
      padding: '10px 14px',
      marginBottom: 16,
      display: 'flex',
      gap: 16,
      alignItems: 'center',
      flexWrap: 'wrap',
      fontSize: 12,
    }}>
      <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>
        {filename} — {total} unique articles
      </span>

      {/* Abstract enrichment progress */}
      {enrichment && enrichableTotal !== null && enrichableTotal > 0 && (
        enrichment.pending > 0 ? (
          <span style={{ color: '#633806' }}>
            ⏳ Fetching abstracts… {enrichment.enriched} / {enrichableTotal}
          </span>
        ) : enrichment.not_found > 0 ? (
          <span style={{ color: '#27500A' }}>
            ✅ {enrichment.has_abstract} with abstract
            {' '}
            <span style={{ color: '#791F1F' }}>⚠ {enrichment.not_found} not found</span>
          </span>
        ) : (
          <span style={{ color: '#27500A' }}>
            ✅ {enrichment.has_abstract} with abstract
          </span>
        )
      )}

      {/* Fallback abstract count when enrichment not applicable (search results) */}
      {(!enrichment || enrichableTotal === 0) && (() => {
        const hasAbstract = enrichment?.has_abstract ?? articles.filter((a) => a.abstract?.trim()).length
        return (
          <span style={{ color: qualityColour(hasAbstract, total) }}>
            {qualityIcon(hasAbstract, total)}{' '}
            {total - hasAbstract > 0
              ? `${total - hasAbstract} missing abstract`
              : `${hasAbstract} with abstract`}
          </span>
        )
      })()}

      {/* Other quality fields — all use server-side counts */}
      {fields.map(({ label, param, count }) => {
        const missingCount = total - count
        const colour = qualityColour(count, total)
        const icon = qualityIcon(count, total)
        const baseQs = uploadRecordId ? `?upload_record_id=${uploadRecordId}` : '?'
        return (
          <span key={label} style={{ color: colour }}>
            {icon}{' '}
            {missingCount > 0 ? (
              <Link
                to={`${baseQs}&missing=${param}`}
                style={{ color: colour }}
              >
                {missingCount} missing {label}
              </Link>
            ) : (
              `${count} with ${label}`
            )}
          </span>
        )
      })}

      {/* Note when enrichment finished with some not found */}
      {enrichment && enrichment.pending === 0 && enrichment.not_found > 0 && (
        <div style={{
          width: '100%',
          color: 'var(--color-text-secondary)',
          marginTop: 4,
        }}>
          ⓘ{' '}
          <Link
            to={`?upload_record_id=${uploadRecordId}&enrichment_status=not_found`}
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {enrichment.not_found} article{enrichment.not_found !== 1 ? 's' : ''}
          </Link>
          {' '}could not be enriched — abstracts not available from PubMed, Europe PMC,
          or Semantic Scholar. These will be routed to full-text review during screening.
        </div>
      )}
    </div>
  )
}
