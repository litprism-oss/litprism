import { Link, useLocation, useParams } from 'react-router-dom'

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, 'aria-hidden': true } as const

const TABS = [
  { key: 'overview', label: 'Overview', path: '', icon: <path d="M4 11l8-7 8 7v9H4z" /> },
  {
    key: 'search',
    label: 'Search',
    path: '/search',
    icon: (
      <>
        <circle cx="11" cy="11" r="6" />
        <path d="M16 16l4 4" />
      </>
    ),
  },
  { key: 'criteria', label: 'Criteria', path: '/criteria', icon: <path d="M5 12l4 4 10-10" /> },
  { key: 'screening', label: 'Screen', path: '/screening', icon: <path d="M4 6h16M7 12h10M10 18h4" /> },
  { key: 'export', label: 'Export', path: '/export', icon: <path d="M12 4v11M7 11l5 5 5-5M5 20h14" /> },
]

/** Phone navigation for the four-step flow. Secondary pages (uploads, PRISMA, articles)
 *  stay in the menu opened from the top bar. */
export function MobileTabBar() {
  const { projectId } = useParams<{ projectId: string }>()
  const { pathname } = useLocation()
  if (!projectId || projectId === 'new') return null

  const base = `/projects/${projectId}`
  const isActive = (key: string, path: string) =>
    key === 'overview' ? pathname === base || pathname === `${base}/` : pathname.startsWith(base + path)

  return (
    <nav
      aria-label="Review steps"
      style={{
        flexShrink: 0,
        height: 60,
        display: 'grid',
        gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
        background: 'var(--color-background-primary)',
        borderTop: '0.5px solid var(--color-border-secondary)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      {TABS.map((tab) => {
        const active = isActive(tab.key, tab.path)
        return (
          <Link
            key={tab.key}
            to={base + tab.path}
            aria-current={active ? 'page' : undefined}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              textDecoration: 'none',
              fontSize: 11,
              fontWeight: active ? 500 : 400,
              color: active ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" {...stroke}>
              {tab.icon}
            </svg>
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}
