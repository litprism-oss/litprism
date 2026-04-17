import { useState } from 'react'
import type { SearchPreviewResponse } from '@/lib/types'
import { formatCount } from '@/lib/utils'

interface SearchScopePreviewProps {
  data: SearchPreviewResponse | undefined
  isLoading: boolean
  error: Error | null
  lastPreviewedAt: Date | null
  onPreviewAgain: () => void
}

function Skeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            height: '18px',
            borderRadius: '4px',
            background: 'var(--color-border-tertiary)',
            width: i === 3 ? '60%' : '100%',
            animation: 'pulse 1.5s ease-in-out infinite',
          }}
        />
      ))}
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }`}</style>
    </div>
  )
}

function timeAgo(date: Date): string {
  const secs = Math.floor((Date.now() - date.getTime()) / 1000)
  if (secs < 60) return 'just now'
  const mins = Math.floor(secs / 60)
  return `${mins} minute${mins !== 1 ? 's' : ''} ago`
}

const SOURCE_LABELS: Record<string, string> = {
  pubmed: 'PubMed',
  europepmc: 'Europe PMC',
  semanticscholar: 'Semantic Scholar',
}

export function SearchScopePreview({
  data,
  isLoading,
  error,
  lastPreviewedAt,
  onPreviewAgain,
}: SearchScopePreviewProps) {
  const [showAllTitles, setShowAllTitles] = useState(false)

  if (!isLoading && !data && !error) return null

  const panelStyle: React.CSSProperties = {
    background: 'var(--color-background-secondary)',
    border: '0.5px solid var(--color-border-tertiary)',
    borderRadius: 'var(--border-radius-lg)',
    padding: '14px',
    marginBottom: '16px',
  }

  if (isLoading) {
    return (
      <div style={panelStyle}>
        <p style={{ fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)', marginBottom: '10px' }}>
          Estimated scope
        </p>
        <Skeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div style={{ ...panelStyle, border: '0.5px solid #D4880A' }}>
        <p style={{ fontSize: '12px', color: '#8B5E00' }}>Preview failed: {error.message}</p>
      </div>
    )
  }

  if (!data) return null

  const sampleSource = data.sources.find((s) => s.sample_titles.length > 0)
  const sampleTitles = sampleSource?.sample_titles ?? []
  const SHOW_LIMIT = 3

  return (
    <div style={panelStyle}>
      <p style={{ fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)', marginBottom: '10px' }}>
        Estimated scope
      </p>

      {data.sources.map((src) => (
        <div key={src.source}>
          {src.error ? (
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '4px 0',
                fontSize: '13px',
              }}
            >
              <span>{SOURCE_LABELS[src.source] ?? src.source}</span>
              <span style={{ fontSize: '12px', color: '#8B5E00' }}>{src.error}</span>
            </div>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: '13px' }}>
              <span style={{ color: 'var(--color-text-primary)' }}>
                {SOURCE_LABELS[src.source] ?? src.source}
              </span>
              <span style={{ fontWeight: 500 }}>~{formatCount(src.estimated_count)}</span>
            </div>
          )}
        </div>
      ))}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          padding: '8px 0 0',
          marginTop: '6px',
          borderTop: '0.5px solid var(--color-border-tertiary)',
          fontSize: '13px',
          fontWeight: 500,
        }}
      >
        <span>Total estimated</span>
        <span>~{formatCount(data.total_estimated)}</span>
      </div>

      {sampleTitles.length > 0 && (
        <div style={{ marginTop: '10px' }}>
          <p
            style={{
              fontSize: '11px',
              color: 'var(--color-text-secondary)',
              marginBottom: '4px',
            }}
          >
            Sample titles ({SOURCE_LABELS[sampleSource?.source ?? ''] ?? sampleSource?.source}):
          </p>
          {(showAllTitles ? sampleTitles : sampleTitles.slice(0, SHOW_LIMIT)).map((title, i) => (
            <p
              key={i}
              style={{
                fontSize: '12px',
                color: 'var(--color-text-secondary)',
                padding: '2px 0',
                margin: 0,
              }}
            >
              &bull; {title}
            </p>
          ))}
          {sampleTitles.length > SHOW_LIMIT && (
            <button
              onClick={() => setShowAllTitles((v) => !v)}
              style={{
                fontSize: '11px',
                color: 'var(--color-text-secondary)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '4px 0 0',
              }}
            >
              {showAllTitles ? 'Show less' : `Show ${sampleTitles.length - SHOW_LIMIT} more`}
            </button>
          )}
        </div>
      )}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '10px',
          paddingTop: '8px',
          borderTop: '0.5px solid var(--color-border-tertiary)',
        }}
      >
        <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
          {lastPreviewedAt ? `Last previewed: ${timeAgo(lastPreviewedAt)}` : ''}
        </span>
        <button
          onClick={onPreviewAgain}
          style={{
            fontSize: '11px',
            color: 'var(--color-text-secondary)',
            background: 'none',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-md)',
            padding: '2px 8px',
            cursor: 'pointer',
          }}
        >
          Preview again
        </button>
      </div>
    </div>
  )
}
