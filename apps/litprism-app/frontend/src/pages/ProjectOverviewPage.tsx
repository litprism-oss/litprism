import { useNavigate, useParams } from 'react-router-dom'
import { useProject } from '@/hooks/useProjects'
import { useSearchRuns } from '@/hooks/useSearchRuns'
import { StepIndicator } from '@/components/common/StepIndicator'
import { StatCard } from '@/components/common/StatCard'
import type { ReviewType } from '@/lib/types'

const REVIEW_TYPE_LABELS: Record<ReviewType, string> = {
  systematic:   'Systematic',
  scoping:      'Scoping',
  rapid:        'Rapid',
  literature:   'Literature',
  state_of_art: 'State of the art',
}

const REVIEW_TYPE_COLOURS: Record<ReviewType, { bg: string; text: string }> = {
  systematic:   { bg: '#E6F1FB', text: '#0C447C' },
  scoping:      { bg: '#E1F5EE', text: '#085041' },
  rapid:        { bg: '#FAEEDA', text: '#633806' },
  literature:   { bg: '#EEEDFE', text: '#3C3489' },
  state_of_art: { bg: '#F1EFE8', text: '#444441' },
}

export function ProjectOverviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const { data: project, isLoading: projectLoading } = useProject(projectId ?? '')
  const { data: searchRuns } = useSearchRuns(projectId ?? '')

  const completedRun = searchRuns?.find((r) => r.status === 'completed')
  const lockedRun = searchRuns?.find((r) => r.status === 'locked')
  const hasCompletedSearch = !!completedRun

  const currentStep: 1 | 2 | 3 = hasCompletedSearch ? 2 : 1

  const articleCount = completedRun?.source_queries?.reduce(
    (sum, sq) => sum + sq.result_count, 0,
  ) ?? (hasCompletedSearch ? 0 : undefined)

  function handleCTA() {
    const base = `/projects/${projectId}`
    if (!searchRuns?.length || searchRuns.every((r) => r.status === 'draft')) {
      navigate(`${base}/search`)
    } else if (lockedRun) {
      navigate(`${base}/search`)
    } else if (hasCompletedSearch) {
      navigate(`${base}/criteria`)
    } else {
      navigate(`${base}/search`)
    }
  }

  const ctaLabel = (() => {
    if (!searchRuns?.length || searchRuns.every((r) => r.status === 'draft')) return 'Start searching →'
    if (lockedRun) return 'View search progress →'
    if (hasCompletedSearch) return 'Set up screening →'
    return 'Start searching →'
  })()

  if (projectLoading) {
    return (
      <div>
        <div style={{ height: 20, width: 200, background: 'var(--color-background-secondary)', borderRadius: 4, marginBottom: 24 }} />
        <div style={{ height: 40, background: 'var(--color-background-secondary)', borderRadius: 8, marginBottom: 24 }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {[0, 1, 2].map((i) => <StatCard key={i} label="" />)}
        </div>
      </div>
    )
  }

  if (!project) return null

  const reviewColours = REVIEW_TYPE_COLOURS[project.review_type]

  return (
    <div>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <p style={{ fontSize: 16, fontWeight: 500, color: 'var(--color-text-primary)' }}>
          {project.name}
        </p>
        <span style={{
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 99,
          background: reviewColours.bg,
          color: reviewColours.text,
        }}>
          {REVIEW_TYPE_LABELS[project.review_type]}
        </span>
      </div>

      {/* Step indicator */}
      <StepIndicator currentStep={currentStep} />

      {/* Stat cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 12,
        marginBottom: 24,
      }}>
        <StatCard label="Articles"  value={articleCount ?? 0} />
        <StatCard label="Screened"  value={0} />
        <StatCard label="Included"  value={0} />
      </div>

      {/* CTA */}
      <button
        onClick={handleCTA}
        style={{
          background: 'var(--color-text-primary)',
          color: 'var(--color-background-primary)',
          border: 'none',
          padding: '9px 18px',
          borderRadius: 'var(--border-radius-md)',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        {ctaLabel}
      </button>
    </div>
  )
}
