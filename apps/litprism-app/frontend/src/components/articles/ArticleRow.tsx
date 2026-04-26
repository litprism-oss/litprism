import { useState } from 'react'
import type { ArticleOut } from '@/lib/types'

const SOURCE_COLOURS: Record<string, { bg: string; text: string }> = {
  pubmed:          { bg: '#E6F1FB', text: '#0C447C' },
  europepmc:       { bg: '#E1F5EE', text: '#085041' },
  semanticscholar: { bg: '#EEEDFE', text: '#3C3489' },
  upload:          { bg: '#F1EFE8', text: '#444441' },
}

const SOURCE_LABELS: Record<string, string> = {
  pubmed:          'PubMed',
  europepmc:       'Europe PMC',
  semanticscholar: 'Semantic Scholar',
  upload:          'Upload',
}

function formatAuthors(authors: ArticleOut['authors']): string {
  if (!authors || authors.length === 0) return ''
  const names = authors.slice(0, 3).map((a) => {
    const fore = a.fore_name ? a.fore_name[0] + ' ' : ''
    return `${fore}${a.last_name}`
  })
  return authors.length > 3 ? names.join(', ') + ' et al.' : names.join(', ')
}

interface ArticleRowProps {
  article: ArticleOut
}

export function ArticleRow({ article }: ArticleRowProps) {
  const [expanded, setExpanded] = useState(false)

  const sourceColour = SOURCE_COLOURS[article.source] ?? SOURCE_COLOURS.upload
  const sourceLabel = SOURCE_LABELS[article.source] ?? article.source

  const authorStr = formatAuthors(article.authors)
  const year = article.publication_year ?? (article.pub_date ? article.pub_date.slice(0, 4) : null)

  const meta = [authorStr, article.journal, year].filter(Boolean).join(' · ')

  return (
    <div
      onClick={() => setExpanded((v) => !v)}
      style={{
        padding: '12px 0',
        borderBottom: '0.5px solid var(--color-border-tertiary)',
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.background =
          'var(--color-background-secondary)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.background = 'transparent'
      }}
    >
      <p style={{
        fontSize: 13,
        fontWeight: 500,
        color: 'var(--color-text-primary)',
        marginBottom: 4,
        lineHeight: 1.4,
      }}>
        {article.title}
      </p>

      <div style={{
        fontSize: 12,
        color: 'var(--color-text-secondary)',
        display: 'flex',
        gap: 8,
        alignItems: 'center',
        flexWrap: 'wrap',
      }}>
        <span style={{
          fontSize: 11,
          padding: '1px 7px',
          borderRadius: 99,
          background: sourceColour.bg,
          color: sourceColour.text,
        }}>
          {sourceLabel}
        </span>

        {meta && <span>{meta}</span>}

        {article.pmid && (
          <a
            href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: 11, color: '#378ADD', textDecoration: 'none' }}
          >
            PMID {article.pmid} ↗
          </a>
        )}

        {article.doi && (
          <a
            href={`https://doi.org/${article.doi}`}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: 11, color: '#378ADD', textDecoration: 'none' }}
          >
            DOI ↗
          </a>
        )}
      </div>

      {expanded && (
        article.abstract ? (
          <p style={{
            fontSize: 12,
            color: 'var(--color-text-secondary)',
            lineHeight: 1.6,
            marginTop: 8,
            paddingTop: 8,
            borderTop: '0.5px solid var(--color-border-tertiary)',
          }}>
            {article.abstract}
          </p>
        ) : (
          <p style={{
            fontSize: 12,
            color: 'var(--color-text-tertiary)',
            fontStyle: 'italic',
            marginTop: 8,
          }}>
            [No abstract available]
          </p>
        )
      )}
    </div>
  )
}
