import { Link, useNavigate, useLocation, useParams } from 'react-router-dom'
import { useSearchRuns } from '@/hooks/useSearchRuns'
import { useUploads } from '@/hooks/useUpload'
import { useCriteria, useCriteriaHistory } from '@/hooks/useCriteria'
import { useScreeningRuns } from '@/hooks/useScreening'

interface NavItemProps {
  label: string
  to: string
  active: boolean
}

function NavItem({ label, to, active }: NavItemProps) {
  const navigate = useNavigate()
  return (
    <div
      onClick={() => navigate(to)}
      style={{
        display: 'block',
        padding: active ? '7px 16px 7px 14px' : '7px 16px',
        fontSize: 13,
        color: active ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
        fontWeight: active ? 500 : 400,
        background: active ? 'var(--color-background-secondary)' : 'transparent',
        borderLeft: active ? '2px solid var(--color-text-primary)' : '2px solid transparent',
        cursor: 'pointer',
      }}
    >
      {label}
    </div>
  )
}

interface SubItemProps {
  label: string
  to: string
  active: boolean
}

function SubItem({ label, to, active }: SubItemProps) {
  return (
    <Link
      to={to}
      style={{
        display: 'block',
        padding: '5px 16px 5px 28px',
        fontSize: 12,
        color: active ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
        fontWeight: active ? 500 : 400,
        background: active ? 'var(--color-background-secondary)' : 'transparent',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        textDecoration: 'none',
        borderLeft: active ? '2px solid var(--color-text-primary)' : '2px solid transparent',
      }}
      onMouseEnter={(e) => {
        if (!active)
          (e.currentTarget as HTMLAnchorElement).style.background =
            'var(--color-background-secondary)'
      }}
      onMouseLeave={(e) => {
        if (!active)
          (e.currentTarget as HTMLAnchorElement).style.background = 'transparent'
      }}
    >
      · {label}
    </Link>
  )
}

export function ProjectSidebar() {
  const { projectId } = useParams<{ projectId: string }>()
  const { pathname, search } = useLocation()

  const { data: searchRuns } = useSearchRuns(projectId ?? '')
  const { data: uploads } = useUploads(projectId ?? '')
  const { data: activeCriteria } = useCriteria(projectId ?? '')
  const { data: criteriaHistory } = useCriteriaHistory(projectId ?? '')
  const { data: screeningRuns } = useScreeningRuns(projectId ?? '')

  if (!projectId || projectId === 'new') return null

  const base = `/projects/${projectId}`
  const currentUrl = pathname + search

  const active = (segment: string) =>
    pathname.includes(`${base}/${segment}`) ||
    (segment === 'overview' && (pathname === base || pathname === `${base}/`))

  const completedRun = Array.isArray(searchRuns)
    ? searchRuns.find((r) => r.status === 'completed')
    : undefined

  const sourceSubItems =
    completedRun?.source_queries?.map((sq) => {
      const to = `${base}/articles?source_query_id=${sq.id}`
      return {
        id: sq.id,
        label: `${sq.source} · ${sq.result_count.toLocaleString()}`,
        to,
        active: currentUrl === to,
      }
    }) ?? []

  const latestScreeningRun =
    Array.isArray(screeningRuns) && screeningRuns.length > 0
      ? [...screeningRuns].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        )[0]
      : undefined

  const uploadSubItems = Array.isArray(uploads)
    ? uploads.map((u) => {
        const name = u.filename.length > 14 ? u.filename.slice(0, 12) + '…' : u.filename
        const to = `${base}/articles?upload_record_id=${u.id}`
        return {
          id: u.id,
          label: `${name} · ${u.record_count.toLocaleString()}`,
          to,
          active: currentUrl === to,
        }
      })
    : []

  return (
    <nav style={{
      width: 160,
      borderRight: '0.5px solid var(--color-border-tertiary)',
      padding: '12px 0',
      overflowY: 'auto',
      flexShrink: 0,
    }}>
      <div>
        <NavItem label="Overview" to={base}             active={active('overview')} />
        <NavItem label="Search"   to={`${base}/search`} active={active('search')} />
        {sourceSubItems.map((item) => (
          <SubItem key={item.id} label={item.label} to={item.to} active={item.active} />
        ))}
        <NavItem label="Screen"   to={`${base}/screening`} active={active('screening')} />
        {latestScreeningRun && (() => {
          const cv = criteriaHistory?.find((c) => c.id === latestScreeningRun.criteria_id)
          const vLabel = cv ? `v${cv.version}` : ''
          const statusLabel =
            latestScreeningRun.status === 'running'
              ? `${latestScreeningRun.screened_count.toLocaleString()} / ${latestScreeningRun.total_articles.toLocaleString()}`
              : latestScreeningRun.status
          return (
            <SubItem
              label={[vLabel, statusLabel].filter(Boolean).join(' · ')}
              to={`${base}/screening`}
              active={false}
            />
          )
        })()}
        <NavItem label="Export"   to={`${base}/export`}    active={active('export')} />
      </div>

      <div style={{
        height: '0.5px',
        background: 'var(--color-border-tertiary)',
        margin: '8px 16px',
      }} />

      <div>
        <NavItem label="Uploads"  to={`${base}/upload`}   active={active('upload')} />
        {uploadSubItems.map((item) => (
          <SubItem key={item.id} label={item.label} to={item.to} active={item.active} />
        ))}
        <NavItem label="Criteria" to={`${base}/criteria`} active={active('criteria')} />
        {activeCriteria && (
          <SubItem
            label={`v${activeCriteria.version} · active`}
            to={`${base}/criteria`}
            active={false}
          />
        )}
        <NavItem label="PRISMA"   to={`${base}/prisma`}   active={active('prisma')} />
      </div>
    </nav>
  )
}
