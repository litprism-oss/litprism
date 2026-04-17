import { useState } from 'react'
import { toast } from 'sonner'
import { translateQuery } from '@/lib/utils'

interface QueryPreviewProps {
  query: string
}

type TranslationSource = 'scopus' | 'wos' | 'europepmc' | 'embase'

const TRANSLATION_SOURCES: { key: TranslationSource; label: string }[] = [
  { key: 'scopus', label: 'Scopus' },
  { key: 'wos', label: 'WoS' },
  { key: 'europepmc', label: 'Europe PMC' },
  { key: 'embase', label: 'Embase' },
]

export function QueryPreview({ query }: QueryPreviewProps) {
  const [copied, setCopied] = useState<string | null>(null)

  if (!query.trim()) return null

  const handleCopy = async (source: TranslationSource | 'pubmed', text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(source)
    toast.success(`Copied ${source === 'pubmed' ? 'PubMed' : TRANSLATION_SOURCES.find(s => s.key === source)?.label} query to clipboard`)
    setTimeout(() => setCopied(null), 1500)
  }

  return (
    <div style={{ marginBottom: '16px' }}>
      {/* Generated PubMed query */}
      <div
        style={{
          background: 'var(--color-background-secondary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-md)',
          padding: '12px 14px',
          marginBottom: '12px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
          <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>Generated PubMed query</span>
          <button
            onClick={() => handleCopy('pubmed', query)}
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
            {copied === 'pubmed' ? 'Copied' : 'Copy for PubMed web'}
          </button>
        </div>
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--color-text-primary)',
            lineHeight: '1.5',
            margin: 0,
          }}
        >
          {query}
        </p>
      </div>

      {/* Translations */}
      <div>
        {TRANSLATION_SOURCES.map(({ key, label }) => {
          const translated = translateQuery(query, key)
          return (
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
                title={translated}
              >
                {translated}
              </span>
              <button
                onClick={() => handleCopy(key, translated)}
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
          )
        })}
      </div>
    </div>
  )
}
