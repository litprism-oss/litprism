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

  const lockedRun = searchRuns?.find((r) => r.status === 'locked')

  const articleCount = project?.article_count ?? 0
  const screenedCount = project?.screened_count ?? 0
  const includedCount = project?.included_count ?? 0

  // Step is derived from real data, so uploads count the same as API searches.
  const currentStep: 1 | 2 | 3 = screenedCount > 0 ? 3 : articleCount > 0 ? 2 : 1

  function nextAction(): { label: string; path: string } {
    const base = `/projects/${projectId}`
    if (lockedRun) return { label: 'View search progress →', path: `${base}/search` }
    if (articleCount === 0) return { label: 'Start searching →', path: `${base}/search` }
    if (!project?.has_criteria) return { label: 'Set up criteria →', path: `${base}/criteria` }
    if (screenedCount === 0) return { label: 'Start screening →', path: `${base}/screening` }
    return { label: 'View results →', path: `${base}/screening/results` }
  }
  const cta = nextAction()

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
        <StatCard label="Articles"  value={articleCount} />
        <StatCard label="Screened"  value={screenedCount} />
        <StatCard label="Included"  value={includedCount} />
      </div>

      {/* CTA */}
      <button
        onClick={() => navigate(cta.path)}
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
        {cta.label}
      </button>
    </div>
  )
}
