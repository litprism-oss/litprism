import { useState } from 'react'
import { toast } from 'sonner'
import { translateQuery } from '@/lib/utils'

interface QueryPreviewProps {
  canonicalQuery: string
  mode: 'pico' | 'freetext'
}

export function QueryPreview({ canonicalQuery }: QueryPreviewProps) {
  const [copied, setCopied] = useState<string | null>(null)

  if (!canonicalQuery.trim()) return null

  const rows = [
    { key: 'pubmedweb', label: 'PubMed web', query: canonicalQuery },
    { key: 'scopus',    label: 'Scopus',     query: translateQuery(canonicalQuery, 'scopus') },
    { key: 'wos',       label: 'WoS',        query: translateQuery(canonicalQuery, 'wos') },
    { key: 'europepmc', label: 'Europe PMC', query: translateQuery(canonicalQuery, 'europepmc') },
    { key: 'embase',    label: 'Embase',     query: translateQuery(canonicalQuery, 'embase') },
  ]

  const handleCopy = async (key: string, label: string, text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(key)
    toast.success(`Copied ${label} query to clipboard`)
    setTimeout(() => setCopied(null), 1500)
  }

  return (
    <div style={{ marginBottom: '16px' }}>
      {rows.map(({ key, label, query }) => (
        <div
          key={key}
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '6px 0',
            borderBottom: '0.5px solid var(--color-border-tertiary)',
          }}
        >
          <span
            style={{
              fontSize: '12px',
              fontWeight: 500,
              color: 'var(--color-text-secondary)',
              width: '80px',
              flexShrink: 0,
            }}
          >
            {label}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--color-text-primary)',
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              margin: '0 10px',
            }}
            title={query}
          >
            {query}
          </span>
          <button
            onClick={() => handleCopy(key, label, query)}
            style={{
              fontSize: '11px',
              color: 'var(--color-text-secondary)',
              border: '0.5px solid var(--color-border-tertiary)',
              background: 'none',
              padding: '2px 8px',
              borderRadius: 'var(--border-radius-md)',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            {copied === key ? 'Copied' : 'Copy'}
          </button>
        </div>
      ))}
    </div>
  )
}
