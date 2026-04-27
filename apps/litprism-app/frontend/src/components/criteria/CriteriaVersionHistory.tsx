import { useState } from 'react'
import type { CriteriaOut } from '@/lib/types'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

interface VersionRowProps {
  criteria: CriteriaOut
}

function VersionRow({ criteria }: VersionRowProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{ borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 0',
          cursor: 'pointer',
          fontSize: '12px',
          color: 'var(--color-text-secondary)',
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <span>
          {expanded ? '▼' : '▶'}&nbsp;&nbsp;v{criteria.version} — {formatDate(criteria.created_at)}{' '}
          — {criteria.inclusion.length} inclusion · {criteria.exclusion.length} exclusion
        </span>
        {criteria.is_active && (
          <span
            style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '99px',
              background: '#EAF3DE',
              color: '#27500A',
              flexShrink: 0,
              marginLeft: '12px',
            }}
          >
            Active
          </span>
        )}
      </div>
      {expanded && (
        <div style={{ paddingBottom: '10px', paddingLeft: '16px' }}>
          {criteria.inclusion.length > 0 && (
            <div style={{ marginBottom: '8px' }}>
              <p
                style={{
                  fontSize: '11px',
                  fontWeight: 500,
                  color: 'var(--color-text-tertiary)',
                  marginBottom: '4px',
                }}
              >
                Inclusion
              </p>
              {criteria.inclusion.map((item, i) => (
                <p
                  key={i}
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-text-secondary)',
                    padding: '2px 0',
                  }}
                >
                  {item}
                </p>
              ))}
            </div>
          )}
          {criteria.exclusion.length > 0 && (
            <div>
              <p
                style={{
                  fontSize: '11px',
                  fontWeight: 500,
                  color: 'var(--color-text-tertiary)',
                  marginBottom: '4px',
                }}
              >
                Exclusion
              </p>
              {criteria.exclusion.map((item, i) => (
                <p
                  key={i}
                  style={{
                    fontSize: '12px',
                    color: 'var(--color-text-secondary)',
                    padding: '2px 0',
                  }}
                >
                  {item}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface CriteriaVersionHistoryProps {
  versions: CriteriaOut[]
}

export function CriteriaVersionHistory({ versions }: CriteriaVersionHistoryProps) {
  const [open, setOpen] = useState(false)

  if (versions.length === 0) return null

  const sorted = [...versions].sort((a, b) => b.version - a.version)

  return (
    <div style={{ marginTop: '24px' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          fontSize: '12px',
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'none',
          border: 'none',
          padding: 0,
          marginBottom: open ? '12px' : 0,
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.color = 'var(--color-text-primary)')
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.color = 'var(--color-text-secondary)')
        }
      >
        {open ? '▼' : '▶'} Version history
      </button>
      {open && (
        <div>
          {sorted.map((v) => (
            <VersionRow key={v.id} criteria={v} />
          ))}
        </div>
      )}
    </div>
  )
}
