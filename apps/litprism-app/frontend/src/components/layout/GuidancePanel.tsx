import { useLocation } from 'react-router-dom'
import { useUIStore } from '@/store/useUIStore'
import { GUIDE_CONTENT } from '@/lib/guideContent'

function routeToKey(pathname: string): string {
  if (pathname.includes('/search')) return 'search'
  if (pathname.includes('/upload')) return 'upload'
  if (pathname.includes('/criteria')) return 'criteria'
  if (pathname.includes('/screening')) return 'screening'
  if (pathname.includes('/export')) return 'export'
  if (pathname.includes('/prisma')) return 'prisma'
  return 'overview'
}

export function GuidancePanel() {
  const { guideEnabled } = useUIStore()
  const { pathname } = useLocation()

  if (!guideEnabled) return null

  const key = routeToKey(pathname)
  const content = GUIDE_CONTENT[key]
  if (!content) return null

  return (
    <aside style={{
      width: 240,
      borderLeft: '0.5px solid var(--color-border-tertiary)',
      padding: '20px 16px',
      flexShrink: 0,
      overflowY: 'auto',
    }}>
      <p style={{
        fontSize: 10,
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        color: 'var(--color-text-tertiary)',
        marginBottom: 8,
      }}>
        Methodology guide
      </p>
      <p style={{
        fontSize: 13,
        fontWeight: 500,
        color: 'var(--color-text-primary)',
        marginBottom: 12,
      }}>
        {content.title}
      </p>
      {content.sections.map((s, i) => (
        <div key={i}>
          {i > 0 && (
            <div style={{
              height: '0.5px',
              background: 'var(--color-border-tertiary)',
              margin: '14px 0',
            }} />
          )}
          <p style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            marginBottom: 6,
          }}>
            {s.heading}
          </p>
          <p style={{
            fontSize: 12,
            color: 'var(--color-text-secondary)',
            lineHeight: 1.6,
          }}>
            {s.body}
          </p>
        </div>
      ))}
      {content.links?.map((l, i) => (
        <div key={i} style={{ marginTop: 14 }}>
          <a
            href={l.url}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: 12, color: '#378ADD' }}
          >
            {l.label} →
          </a>
        </div>
      ))}
    </aside>
  )
}
