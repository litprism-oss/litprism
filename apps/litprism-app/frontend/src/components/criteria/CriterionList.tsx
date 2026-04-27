import { useRef } from 'react'

interface CriterionListProps {
  label: string
  items: string[]
  onChange: (items: string[]) => void
  type: 'inclusion' | 'exclusion'
}

export function CriterionList({ label, items, onChange, type }: CriterionListProps) {
  const addBtnRef = useRef<HTMLButtonElement>(null)

  function update(index: number, value: string) {
    const next = [...items]
    next[index] = value
    onChange(next)
  }

  function remove(index: number) {
    onChange(items.filter((_, i) => i !== index))
  }

  function add() {
    onChange([...items, ''])
    // Focus the new input on the next render tick
    setTimeout(() => {
      const inputs = document.querySelectorAll<HTMLInputElement>(
        `[data-criterion-list="${type}"] input`,
      )
      inputs[inputs.length - 1]?.focus()
    }, 0)
  }

  const borderColor = type === 'inclusion' ? '#639922' : '#791F1F'
  const addLabel = type === 'inclusion' ? 'Add inclusion criterion' : 'Add exclusion criterion'

  return (
    <div style={{ marginBottom: '24px' }}>
      <p
        style={{
          fontSize: '12px',
          fontWeight: 500,
          color: 'var(--color-text-secondary)',
          marginBottom: '8px',
        }}
      >
        {label}
      </p>
      <div
        data-criterion-list={type}
        style={{ borderLeft: `2px solid ${borderColor}`, paddingLeft: '12px' }}
      >
        {items.map((item, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '7px 0',
              borderBottom: '0.5px solid var(--color-border-tertiary)',
            }}
          >
            <input
              value={item}
              onChange={(e) => update(i, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  add()
                }
              }}
              style={{
                flex: 1,
                fontSize: '13px',
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-primary)',
                outline: 'none',
                padding: '0',
              }}
              onFocus={(e) => {
                e.currentTarget.style.background = 'var(--color-background-secondary)'
                e.currentTarget.style.borderRadius = 'var(--border-radius-md)'
                e.currentTarget.style.padding = '2px 6px'
              }}
              onBlur={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.borderRadius = '0'
                e.currentTarget.style.padding = '0'
              }}
              placeholder="Enter criterion…"
            />
            <button
              onClick={() => remove(i)}
              style={{
                fontSize: '12px',
                color: 'var(--color-text-tertiary)',
                cursor: 'pointer',
                padding: '2px 4px',
                border: 'none',
                background: 'none',
                flexShrink: 0,
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = 'var(--color-text-primary)')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = 'var(--color-text-tertiary)')
              }
              aria-label="Remove criterion"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      <button
        ref={addBtnRef}
        onClick={add}
        style={{
          fontSize: '12px',
          color: 'var(--color-text-secondary)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '6px 0',
          marginTop: '4px',
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.color = 'var(--color-text-primary)')
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.color = 'var(--color-text-secondary)')
        }
      >
        + {addLabel}
      </button>
    </div>
  )
}
