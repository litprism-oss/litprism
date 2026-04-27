import { useParams } from 'react-router-dom'
import { useScreeningRuns, useStartScreening, useCancelScreening } from '@/hooks/useScreening'
import { useSearchProgress } from '@/hooks/useSearchProgress'
import { useCriteria } from '@/hooks/useCriteria'
import { ScreeningSetupForm } from '@/components/screening/ScreeningSetupForm'
import { ScreeningProgress } from '@/components/screening/ScreeningProgress'
import { ScreeningCompleteSummary } from '@/components/screening/ScreeningCompleteSummary'

export function ScreeningPage() {
  const { projectId = '' } = useParams()
  const { data: runs, isLoading } = useScreeningRuns(projectId)
  const { data: activeCriteria } = useCriteria(projectId)
  const { events } = useSearchProgress(projectId)
  const startScreening = useStartScreening(projectId)
  const cancelScreening = useCancelScreening(projectId)

  const screeningEvents = events.filter(
    (e) =>
      e.event === 'screening_progress' ||
      e.event === 'screening_complete' ||
      e.event === 'screening_error',
  )

  if (isLoading) {
    return (
      <div style={{ padding: '24px', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
        Loading…
      </div>
    )
  }

  const latestRun = runs && runs.length > 0
    ? [...runs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
    : null

  // no run yet → setup form
  if (!latestRun) {
    return <ScreeningSetupForm projectId={projectId} />
  }

  // pending → queued spinner
  if (latestRun.status === 'pending') {
    return (
      <div style={{ padding: '24px', maxWidth: '600px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
          <p style={{ fontSize: '15px', fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
            Queued…
          </p>
          <button
            onClick={() => cancelScreening.mutate(latestRun.id)}
            disabled={cancelScreening.isPending}
            style={{
              fontSize: '12px',
              border: '0.5px solid var(--color-border-secondary)',
              background: 'none',
              padding: '5px 12px',
              borderRadius: 'var(--border-radius-md)',
              cursor: cancelScreening.isPending ? 'not-allowed' : 'pointer',
              color: 'var(--color-text-secondary)',
              opacity: cancelScreening.isPending ? 0.6 : 1,
            }}
          >
            Cancel
          </button>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
          Screening is queued and will start shortly.
        </p>
      </div>
    )
  }

  // running, paused, or cancelled/paused (resume in flight) → progress view
  if (latestRun.status === 'running' || latestRun.status === 'paused' || latestRun.status === 'cancelled') {
    return (
      <ScreeningProgress
        projectId={projectId}
        run={latestRun}
        events={screeningEvents}
      />
    )
  }

  // completed → if criteria changed, show previous summary + setup form for new run
  if (latestRun.status === 'completed') {
    const criteriaUpdated = activeCriteria && activeCriteria.id !== latestRun.criteria_id
    if (criteriaUpdated) {
      return (
        <div>
          <div style={{ borderBottom: '0.5px solid var(--color-border-tertiary)', marginBottom: '0' }}>
            <div style={{ padding: '12px 24px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)' }}>
                Previous run
              </span>
              <span style={{ fontSize: '12px', color: 'var(--color-text-tertiary)' }}>
                Criteria updated — start a new screening run below
              </span>
            </div>
            <div style={{ opacity: 0.6, pointerEvents: 'none' }}>
              <ScreeningCompleteSummary projectId={projectId} run={latestRun} />
            </div>
          </div>
          <ScreeningSetupForm projectId={projectId} />
        </div>
      )
    }
    return <ScreeningCompleteSummary projectId={projectId} run={latestRun} />
  }

  // failed → error + retry
  return (
    <div style={{ padding: '24px', maxWidth: '600px' }}>
      <p style={{ fontSize: '15px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
        Screening failed
      </p>
      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
        The screening run encountered an error and could not complete.
      </p>
      <button
        onClick={() => startScreening.mutate({})}
        disabled={startScreening.isPending}
        style={{
          fontSize: '13px',
          fontWeight: 500,
          padding: '8px 18px',
          background: 'var(--color-text-primary)',
          color: 'var(--color-background-primary)',
          border: 'none',
          borderRadius: 'var(--border-radius-md)',
          cursor: startScreening.isPending ? 'not-allowed' : 'pointer',
          opacity: startScreening.isPending ? 0.6 : 1,
        }}
      >
        {startScreening.isPending ? 'Starting…' : 'Retry screening'}
      </button>
    </div>
  )
}
