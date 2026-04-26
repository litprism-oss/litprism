import type { ArticleOut, ArticleQualitySummary } from '@/lib/types'

function computeQuality(articles: ArticleOut[]): ArticleQualitySummary {
  const total = articles.length
  return {
    total,
    has_title:    articles.filter((a) => a.title?.trim()).length,
    has_abstract: articles.filter((a) => a.abstract?.trim()).length,
    has_authors:  articles.filter((a) => a.authors?.length > 0).length,
    has_doi:      articles.filter((a) => a.doi?.trim()).length,
  }
}

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
}

export function ArticleQualityBanner({ filename, articles }: ArticleQualityBannerProps) {
  const q = computeQuality(articles)

  const fields: Array<{ label: string; count: number }> = [
    { label: 'titles',    count: q.has_title },
    { label: 'abstracts', count: q.has_abstract },
    { label: 'authors',   count: q.has_authors },
    { label: 'DOIs',      count: q.has_doi },
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
        {filename} — {q.total} records parsed
      </span>

      {fields.map(({ label, count }) => {
        const missing = q.total - count
        const colour = qualityColour(count, q.total)
        const icon = qualityIcon(count, q.total)
        return (
          <span key={label} style={{ color: colour }}>
            {icon}{' '}
            {missing > 0
              ? `${missing} missing ${label}`
              : `${count} ${label}`}
          </span>
        )
      })}
    </div>
  )
}
