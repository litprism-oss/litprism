import { useNavigate, useParams } from 'react-router-dom'
import { useProject } from '@/hooks/useProjects'
import { useSearchRuns } from '@/hooks/useSearchRuns'
import { useScreeningResults } from '@/hooks/useScreeningResults'
import { nextAction } from '@/lib/nextAction'
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

  const cta = project ? nextAction(project, !!lockedRun) : { label: 'Start searching', path: '' }
  const { data: uncertainData } = useScreeningResults(projectId ?? '', {
    decision: 'uncertain',
    page: 1,
    page_size: 1,
  })
  const uncertain = screenedCount > 0 ? (uncertainData?.total ?? 0) : 0

  const nextTitle =
    uncertain > 0
      ? `${uncertain.toLocaleString()} ${uncertain === 1 ? 'article is' : 'articles are'} uncertain`
      : screenedCount > 0
        ? 'Screening is complete'
        : articleCount > 0
          ? project?.has_criteria
            ? 'Ready to screen'
            : 'Add your eligibility criteria'
          : 'Find your articles'
  const nextBody =
    uncertain > 0
      ? 'The model could not decide from the abstract. They are not excluded. Review them yourself or run full-text screening.'
      : screenedCount > 0
        ? 'Check the results, then export your references and the PRISMA search record.'
        : articleCount > 0
          ? project?.has_criteria
            ? 'Each abstract is checked against every criterion, with a quote as evidence.'
            : 'Screening checks every abstract against inclusion and exclusion criteria you write.'
          : 'Search PubMed, Europe PMC and Semantic Scholar, or upload a reference file.'

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

      {/* Next step */}
      <div style={{
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        maxWidth: 560,
      }}>
        <p style={{
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--color-text-secondary)',
        }}>
          Next step
        </p>
        <p style={{ fontSize: 15, fontWeight: 500, lineHeight: 1.4 }}>{nextTitle}</p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>{nextBody}</p>
        <button
          onClick={() => navigate(cta.path)}
          style={{
            minHeight: 44,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 14px',
            background: 'var(--color-text-primary)',
            color: 'var(--color-background-primary)',
            border: 'none',
            borderRadius: 'var(--border-radius-md)',
            fontSize: 14,
            fontWeight: 500,
            fontFamily: 'inherit',
            cursor: 'pointer',
          }}
        >
          <span>{uncertain > 0 ? 'Review uncertain' : cta.label}</span>
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </div>
  )
}
