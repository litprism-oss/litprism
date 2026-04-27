import { useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { ProgressEvent } from '@/hooks/useSearchProgress'
import type { ScreeningRunOut } from '@/lib/types'
import { useCancelScreening } from '@/hooks/useScreening'
import { api } from '@/lib/api'

interface Props {
  projectId: string
  run: ScreeningRunOut
  events: ProgressEvent[]
}

function formatTime(iso: string) {
  return (
    new Date(iso).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
    }) + ' UTC'
  )
}

function DecisionBar({
  label,
  count,
  pct,
  color,
}: {
  label: string
  count: number
  pct: number
  color: string
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', fontSize: '13px' }}>
      <span style={{ width: '80px', color: 'var(--color-text-secondary)' }}>{label}</span>
      <span style={{ width: '40px', fontWeight: 500, color: 'var(--color-text-primary)', textAlign: 'right' }}>
        {count.toLocaleString()}
      </span>
      <div
        style={{
          flex: 1,
          height: '4px',
          background: 'var(--color-background-secondary)',
          borderRadius: '99px',
        }}
      >
        <div
          style={{
            height: '100%',
            borderRadius: '99px',
            background: color,
            width: `${pct}%`,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      <span style={{ width: '36px', fontSize: '12px', color: 'var(--color-text-secondary)', textAlign: 'right' }}>
        {pct}%
      </span>
    </div>
  )
}

export function ScreeningProgress({ projectId, run, events }: Props) {
  const qc = useQueryClient()
  const cancelScreening = useCancelScreening(projectId)
  const resumeScreening = useMutation({
    mutationFn: () => api.screening.resume(projectId, run.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] }),
  })

  const wsStats = useMemo(() => {
    const progressEvents = events.filter((e) => e.event === 'screening_progress')
    if (progressEvents.length === 0) return null

    let included = 0
    let excluded = 0
    let uncertain = 0
    let processed = 0
    let total = 0

    for (const e of events) {
      if (e.event === 'screening_progress') {
        if (e.decision === 'include') included++
        else if (e.decision === 'exclude') excluded++
        else if (e.decision === 'uncertain') uncertain++
        processed = e.processed
        total = e.total
      }
    }

    return { included, excluded, uncertain, processed, total }
  }, [events])

  // Progress bar: prefer WS (live), fall back to polled screened_count
  const processed = wsStats?.processed ?? run.screened_count
  const total = wsStats?.total ?? run.total_articles

  // Decision breakdown: WS events only (not tracked per-decision in DB)
  const included = wsStats?.included ?? 0
  const excluded = wsStats?.excluded ?? 0
  const uncertain = wsStats?.uncertain ?? 0

  const pct = total > 0 ? Math.round((processed / total) * 100) : 0
  const decisioned = included + excluded + uncertain
  const incPct = decisioned > 0 ? Math.round((included / decisioned) * 100) : 0
  const excPct = decisioned > 0 ? Math.round((excluded / decisioned) * 100) : 0
  const uncPct = decisioned > 0 ? Math.round((uncertain / decisioned) * 100) : 0

  const isPaused = run.status === 'paused'

  function handleResume() {
    resumeScreening.mutate()
  }

  function handleCancel() {
    cancelScreening.mutate(run.id)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '600px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
        <span style={{ fontSize: '15px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
          {isPaused ? 'Screening paused' : 'Screening in progress'}
        </span>
        {isPaused ? (
          <button
            onClick={handleResume}
            style={{
              fontSize: '12px',
              border: '0.5px solid var(--color-border-secondary)',
              background: 'none',
              padding: '5px 12px',
              borderRadius: 'var(--border-radius-md)',
              cursor: 'pointer',
              color: 'var(--color-text-primary)',
            }}
          >
            Resume
          </button>
        ) : (
          <button
            onClick={handleCancel}
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
        )}
      </div>

      {run.started_at && (
        <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
          Started {formatTime(run.started_at)}
        </p>
      )}

      {/* Progress bar */}
      <div
        style={{
          height: '10px',
          background: 'var(--color-background-secondary)',
          borderRadius: '99px',
          overflow: 'hidden',
          marginBottom: '8px',
        }}
      >
        <div
          style={{
            height: '100%',
            borderRadius: '99px',
            background: 'var(--color-text-primary)',
            width: `${pct}%`,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '20px', textAlign: 'right' }}>
        {processed.toLocaleString()} / {total.toLocaleString()} articles
      </p>

      {/* Decision breakdown */}
      <p style={{ fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)', marginBottom: '8px' }}>
        Decisions so far
      </p>
      <DecisionBar label="Include" count={included} pct={incPct} color="#639922" />
      <DecisionBar label="Exclude" count={excluded} pct={excPct} color="#791F1F" />
      <DecisionBar label="Uncertain" count={uncertain} pct={uncPct} color="#633806" />

      {run.error_count > 0 && (
        <p style={{ marginTop: '12px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
          Errors: <span style={{ color: '#791F1F', fontWeight: 500 }}>{run.error_count}</span>
        </p>
      )}
    </div>
  )
}
