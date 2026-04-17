import { useState } from 'react'
import { ChevronDown, ChevronRight, X } from 'lucide-react'

export interface SearchFilters {
  date_from?: string
  date_to?: string
  languages?: string[]
  pub_types?: string[]
  species?: string[]
}

interface FilterPanelProps {
  filters: SearchFilters
  onChange: (filters: SearchFilters) => void
}

const SUGGESTED_LANGUAGES = ['English', 'French', 'German', 'Spanish', 'Chinese']
const SUGGESTED_PUB_TYPES = ['Clinical Trial', 'Randomized Controlled Trial', 'Review', 'Systematic Review', 'Meta-Analysis', 'Observational Study']
const SUGGESTED_SPECIES = ['Human', 'Animal']

function TagInput({
  tags,
  suggestions,
  onAdd,
  onRemove,
  placeholder,
}: {
  tags: string[]
  suggestions: string[]
  onAdd: (v: string) => void
  onRemove: (v: string) => void
  placeholder: string
}) {
  const [adding, setAdding] = useState(false)
  const [input, setInput] = useState('')

  const available = suggestions.filter((s) => !tags.includes(s))

  const commit = (v: string) => {
    const val = v.trim()
    if (val && !tags.includes(val)) onAdd(val)
    setInput('')
    setAdding(false)
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
      {tags.map((t) => (
        <span
          key={t}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '12px',
            padding: '2px 8px',
            borderRadius: '99px',
            background: 'var(--color-background-secondary)',
            border: '0.5px solid var(--color-border-secondary)',
            color: 'var(--color-text-primary)',
          }}
        >
          {t}
          <button
            onClick={() => onRemove(t)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1 }}
          >
            <X size={10} color="var(--color-text-secondary)" />
          </button>
        </span>
      ))}
      {adding ? (
        <div style={{ position: 'relative' }}>
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commit(input)
              if (e.key === 'Escape') { setAdding(false); setInput('') }
            }}
            onBlur={() => { if (!input) setAdding(false) }}
            placeholder={placeholder}
            style={{ fontSize: '12px', width: '140px', padding: '2px 6px' }}
          />
          {available.length > 0 && input === '' && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                zIndex: 10,
                background: 'var(--color-background-primary)',
                border: '0.5px solid var(--color-border-secondary)',
                borderRadius: 'var(--border-radius-md)',
                marginTop: '2px',
                minWidth: '160px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            >
              {available.map((s) => (
                <button
                  key={s}
                  onMouseDown={() => commit(s)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '6px 10px',
                    fontSize: '12px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          style={{
            fontSize: '11px',
            color: 'var(--color-text-secondary)',
            background: 'none',
            border: '0.5px dashed var(--color-border-secondary)',
            borderRadius: '99px',
            padding: '2px 8px',
            cursor: 'pointer',
          }}
        >
          + Add
        </button>
      )}
    </div>
  )
}

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false)

  const set = (patch: Partial<SearchFilters>) => onChange({ ...filters, ...patch })
  const addTag = (field: 'languages' | 'pub_types' | 'species', v: string) =>
    set({ [field]: [...(filters[field] ?? []), v] })
  const removeTag = (field: 'languages' | 'pub_types' | 'species', v: string) =>
    set({ [field]: (filters[field] ?? []).filter((x) => x !== v) })

  return (
    <div style={{ marginBottom: '16px' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '13px',
          fontWeight: 500,
          color: 'var(--color-text-primary)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '4px 0',
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Filters
      </button>

      {open && (
        <div
          style={{
            marginTop: '10px',
            padding: '14px',
            background: 'var(--color-background-secondary)',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-md)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {/* Date range */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)', width: '80px', flexShrink: 0 }}>
              Date range
            </span>
            <input
              type="text"
              value={filters.date_from ?? ''}
              onChange={(e) => set({ date_from: e.target.value })}
              placeholder="2015"
              style={{ fontSize: '12px', width: '56px', padding: '3px 6px' }}
            />
            <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>to</span>
            <input
              type="text"
              value={filters.date_to ?? ''}
              onChange={(e) => set({ date_to: e.target.value })}
              placeholder={new Date().getFullYear().toString()}
              style={{ fontSize: '12px', width: '56px', padding: '3px 6px' }}
            />
          </div>

          {/* Language */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)', width: '80px', flexShrink: 0, paddingTop: '3px' }}>
              Language
            </span>
            <TagInput
              tags={filters.languages ?? []}
              suggestions={SUGGESTED_LANGUAGES}
              onAdd={(v) => addTag('languages', v)}
              onRemove={(v) => removeTag('languages', v)}
              placeholder="Add language"
            />
          </div>

          {/* Pub types */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)', width: '80px', flexShrink: 0, paddingTop: '3px' }}>
              Pub types
            </span>
            <TagInput
              tags={filters.pub_types ?? []}
              suggestions={SUGGESTED_PUB_TYPES}
              onAdd={(v) => addTag('pub_types', v)}
              onRemove={(v) => removeTag('pub_types', v)}
              placeholder="Add type"
            />
          </div>

          {/* Species */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span
              style={{ fontSize: '12px', color: 'var(--color-text-secondary)', width: '80px', flexShrink: 0, paddingTop: '3px' }}
            >
              Species
              <span style={{ display: 'block', fontSize: '10px', color: 'var(--color-text-tertiary)' }}>PubMed only</span>
            </span>
            <TagInput
              tags={filters.species ?? []}
              suggestions={SUGGESTED_SPECIES}
              onAdd={(v) => addTag('species', v)}
              onRemove={(v) => removeTag('species', v)}
              placeholder="Add species"
            />
          </div>
        </div>
      )}
    </div>
  )
}
