const SOURCES = ['pubmed', 'europepmc', 'semanticscholar'] as const
type Source = (typeof SOURCES)[number]

const SOURCE_LABELS: Record<Source, string> = {
  pubmed: 'PubMed',
  europepmc: 'Europe PMC',
  semanticscholar: 'Semantic Scholar',
}

interface SourceSelectorProps {
  selected: Source[]
  onChange: (selected: Source[]) => void
}

export function SourceSelector({ selected, onChange }: SourceSelectorProps) {
  const toggle = (source: Source) => {
    if (selected.includes(source)) {
      if (selected.length === 1) return // keep at least one
      onChange(selected.filter((s) => s !== source))
    } else {
      onChange([...selected, source])
    }
  }

  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
      {SOURCES.map((source) => {
        const active = selected.includes(source)
        return (
          <button
            key={source}
            onClick={() => toggle(source)}
            style={{
              fontSize: '12px',
              padding: '5px 12px',
              borderRadius: 'var(--border-radius-md)',
              border: active
                ? '0.5px solid var(--color-text-primary)'
                : '0.5px solid var(--color-border-secondary)',
              background: active ? 'var(--color-text-primary)' : 'transparent',
              color: active ? 'var(--color-background-primary)' : 'var(--color-text-secondary)',
              cursor: selected.length === 1 && active ? 'not-allowed' : 'pointer',
              opacity: selected.length === 1 && active ? 0.6 : 1,
            }}
          >
            {active ? '✓ ' : ''}{SOURCE_LABELS[source]}
          </button>
        )
      })}
    </div>
  )
}
