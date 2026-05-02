import { useState } from 'react'
import { Link, useNavigate, useLocation, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchRuns } from '@/hooks/useSearchRuns'
import { useUploads } from '@/hooks/useUpload'
import { useCriteria, useCriteriaHistory } from '@/hooks/useCriteria'
import { useScreeningRuns } from '@/hooks/useScreening'
import { api } from '@/lib/api'

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
  muted?: boolean
}

function SubItem({ label, to, active, muted }: SubItemProps) {
  return (
    <Link
      to={to}
      style={{
        display: 'block',
        padding: '5px 16px 5px 28px',
        fontSize: 12,
        color: muted
          ? 'var(--color-text-tertiary)'
          : active
            ? 'var(--color-text-primary)'
            : 'var(--color-text-secondary)',
        fontWeight: active ? 500 : 400,
        background: active ? 'var(--color-background-secondary)' : 'transparent',
        cursor: muted ? 'default' : 'pointer',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        textDecoration: 'none',
        borderLeft: active ? '2px solid var(--color-text-primary)' : '2px solid transparent',
        pointerEvents: muted ? 'none' : 'auto',
        opacity: muted ? 0.5 : 1,
      }}
      onMouseEnter={(e) => {
        if (!active && !muted)
          (e.currentTarget as HTMLAnchorElement).style.background =
            'var(--color-background-secondary)'
      }}
      onMouseLeave={(e) => {
        if (!active && !muted)
          (e.currentTarget as HTMLAnchorElement).style.background = 'transparent'
      }}
    >
      · {label}
    </Link>
  )
}

interface RunSubItemProps {
  label: string
  date: string | null
  to: string
  active: boolean
  projectId: string
  runId: string
}

function RunSubItem({ label, date, to, active, projectId, runId }: RunSubItemProps) {
  const [hovered, setHovered] = useState(false)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const deleteMutation = useMutation({
    mutationFn: () => api.screening.deleteRun(projectId, runId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] })
      navigate(`/projects/${projectId}/screening`)
    },
  })

  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Link
        to={to}
        style={{
          display: 'block',
          padding: '5px 32px 5px 28px',
          fontSize: 12,
          color: active ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
          fontWeight: active ? 500 : 400,
          background: hovered || active ? 'var(--color-background-secondary)' : 'transparent',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          textDecoration: 'none',
          borderLeft: active ? '2px solid var(--color-text-primary)' : '2px solid transparent',
        }}
      >
        · {label}
        {date && (
          <span style={{ color: 'var(--color-text-tertiary)', fontWeight: 400 }}> · {date}</span>
        )}
      </Link>
      {hovered && (
        <button
          onClick={(e) => {
            e.preventDefault()
            if (!deleteMutation.isPending &&
              window.confirm('Remove these screening results? You won\'t be able to get them back.'))
              deleteMutation.mutate()
          }}
          title="Remove from list"
          style={{
            position: 'absolute',
            right: 8,
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text-tertiary)',
            fontSize: 14,
            lineHeight: 1,
            padding: '0 2px',
          }}
        >
          ×
        </button>
      )}
    </div>
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
      return { id: sq.id, label: `${sq.source} · ${sq.result_count.toLocaleString()}`, to, active: currentUrl === to }
    }) ?? []

  const uploadSubItems = Array.isArray(uploads)
    ? uploads.map((u) => {
        const name = u.filename.length > 14 ? u.filename.slice(0, 12) + '…' : u.filename
        const to = `${base}/articles?upload_record_id=${u.id}`
        return { id: u.id, label: `${name} · ${u.record_count.toLocaleString()}`, to, active: currentUrl === to }
      })
    : []

  // Build criteriaMap: id → version number
  const criteriaMap = new Map(criteriaHistory?.map((c) => [c.id, c.version]) ?? [])

  // Group all runs by criteria version. Abstract + full-text runs for the same
  // criteria collapse into one sidebar entry.
  type Run = NonNullable<typeof screeningRuns>[number]
  const groupedByCriteria = new Map<string, Run[]>()
  for (const run of screeningRuns ?? []) {
    const group = groupedByCriteria.get(run.criteria_id) ?? []
    group.push(run)
    groupedByCriteria.set(run.criteria_id, group)
  }

  const criteriaEntries = [...groupedByCriteria.entries()]
    .map(([criteriaId, runs]) => {
      const version = criteriaMap.get(criteriaId) ?? '?'
      const hasRunning = runs.some(r => r.status === 'running' || r.status === 'pending')
      const allDone = runs.every(r => r.status === 'completed')
      const latest = [...runs].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )[0]
      const statusLabel = hasRunning ? 'in progress…'
        : allDone ? 'done'
        : latest.status === 'cancelled' || latest.status === 'paused' ? 'paused'
        : latest.status
      // Link to the fulltext completed run if available, otherwise latest completed, otherwise latest
      const linkRun =
        runs.find(r => r.status === 'completed' && r.stage === 'fulltext') ??
        runs.find(r => r.status === 'completed') ??
        latest
      return { criteriaId, version, statusLabel, linkRun, latest }
    })
    .sort((a, b) => {
      const aVer = typeof a.version === 'number' ? a.version : 0
      const bVer = typeof b.version === 'number' ? b.version : 0
      return aVer - bVer
    })

  return (
    <nav
      style={{
        width: '100%',
        minWidth: 220,
        borderRight: '0.5px solid var(--color-border-tertiary)',
        padding: '12px 0',
        overflowY: 'auto',
        flexShrink: 0,
      }}
    >
      <div>
        <NavItem label="Overview" to={base}             active={active('overview')} />
        <NavItem label="Search"   to={`${base}/search`} active={active('search')} />
        {sourceSubItems.map((item) => (
          <SubItem key={item.id} label={item.label} to={item.to} active={item.active} />
        ))}

        {/* Criteria — above Screen */}
        <NavItem label="Criteria" to={`${base}/criteria`} active={active('criteria')} />
        {activeCriteria && (
          <SubItem
            label={`v${activeCriteria.version} · active`}
            to={`${base}/criteria`}
            active={false}
          />
        )}

        {/* Screen — flat run list */}
        <NavItem
          label="Screen"
          to={`${base}/screening`}
          active={active('screening') && !pathname.includes('/results')}
        />
        {criteriaEntries.map(({ criteriaId, version, statusLabel, linkRun, latest }) => {
          const label = `Version ${version} · ${statusLabel}`
          const dateStr = linkRun.completed_at ?? linkRun.created_at
          const date = dateStr
            ? new Date(dateStr).toLocaleDateString('en-GB', { month: 'short', day: 'numeric' })
            : null
          const to = `${base}/screening/results?run_id=${linkRun.id}`
          const isActive = currentUrl.startsWith(`${base}/screening/results`) &&
            (currentUrl.includes(linkRun.id) || currentUrl.includes(latest.id))

          return (
            <RunSubItem
              key={criteriaId}
              label={label}
              date={date}
              to={to}
              active={isActive}
              projectId={projectId}
              runId={latest.id}
            />
          )
        })}

        <NavItem label="Export" to={`${base}/export`} active={active('export')} />
      </div>

      <div
        style={{
          height: '0.5px',
          background: 'var(--color-border-tertiary)',
          margin: '8px 16px',
        }}
      />

      <div>
        <NavItem label="Uploads" to={`${base}/upload`} active={active('upload')} />
        {uploadSubItems.map((item) => (
          <SubItem key={item.id} label={item.label} to={item.to} active={item.active} />
        ))}
        <NavItem label="PRISMA" to={`${base}/prisma`} active={active('prisma')} />
      </div>
    </nav>
  )
}
