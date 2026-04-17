import { useNavigate } from 'react-router-dom'
import type { ProjectOut, SearchRunOut, ReviewType } from '@/lib/types'

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

const STATUS_COLOURS = {
  searching: { bg: '#E6F1FB', text: '#0C447C' },
  complete:  { bg: '#EAF3DE', text: '#27500A' },
  failed:    { bg: '#FCEBEB', text: '#791F1F' },
  draft:     { bg: 'var(--color-background-secondary)', text: 'var(--color-text-secondary)' },
}

function statusBadge(run?: SearchRunOut) {
  if (!run)                  return { label: 'Draft',      colours: STATUS_COLOURS.draft }
  if (run.status === 'locked')    return { label: '● Searching…', colours: STATUS_COLOURS.searching }
  if (run.status === 'completed') return { label: '✓ Complete',   colours: STATUS_COLOURS.complete }
  if (run.status === 'failed')    return { label: 'Search failed', colours: STATUS_COLOURS.failed }
  return { label: 'Draft', colours: STATUS_COLOURS.draft }
}

interface ProjectCardSkeletonProps {
  isLoading: true
}

interface ProjectCardDataProps {
  isLoading?: false
  project: ProjectOut
  latestRun?: SearchRunOut
}

type ProjectCardProps = ProjectCardSkeletonProps | ProjectCardDataProps

export function ProjectCard(props: ProjectCardProps) {
  const navigate = useNavigate()

  if (props.isLoading) {
    return (
      <div style={{
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        padding: 16,
        minHeight: 130,
      }}>
        <div style={{ height: 14, width: '70%', background: 'var(--color-background-secondary)', borderRadius: 4, marginBottom: 10 }} />
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          <div style={{ height: 18, width: 70, background: 'var(--color-background-secondary)', borderRadius: 99 }} />
          <div style={{ height: 18, width: 60, background: 'var(--color-background-secondary)', borderRadius: 99 }} />
        </div>
        <div style={{ height: 28, width: 50, background: 'var(--color-background-secondary)', borderRadius: 4 }} />
      </div>
    )
  }

  const { project, latestRun } = props
  const reviewColours = REVIEW_TYPE_COLOURS[project.review_type]
  const { label: statusLabel, colours: statusColours } = statusBadge(latestRun)

  const articleCount = latestRun?.source_queries?.reduce((sum, sq) => sum + sq.result_count, 0) ?? 0

  return (
    <div
      onClick={() => navigate(`/projects/${project.id}`)}
      style={{
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        padding: 16,
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border-secondary)'
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border-tertiary)'
      }}
    >
      <p style={{
        fontSize: 14,
        fontWeight: 500,
        color: 'var(--color-text-primary)',
        marginBottom: 8,
        lineHeight: 1.4,
      }}>
        {project.name}
      </p>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        <span style={{
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 99,
          background: reviewColours.bg,
          color: reviewColours.text,
        }}>
          {REVIEW_TYPE_LABELS[project.review_type]}
        </span>
        <span style={{
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 99,
          background: statusColours.bg,
          color: statusColours.text,
        }}>
          {statusLabel}
        </span>
      </div>

      <p style={{
        fontSize: 22,
        fontWeight: 500,
        color: 'var(--color-text-primary)',
        marginBottom: 2,
      }}>
        {articleCount.toLocaleString()}
      </p>
      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
        articles
      </p>

      <div style={{
        marginTop: 14,
        paddingTop: 12,
        borderTop: '0.5px solid var(--color-border-tertiary)',
        fontSize: 12,
        color: 'var(--color-text-secondary)',
      }}>
        Created {new Date(project.created_at).toLocaleDateString('en-GB', {
          day: 'numeric', month: 'short', year: 'numeric',
        })}
      </div>
    </div>
  )
}
