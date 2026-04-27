import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useScreeningRuns } from '@/hooks/useScreening'
import { useScreeningResults } from '@/hooks/useScreeningResults'
import { useCriteriaHistory } from '@/hooks/useCriteria'
import { ResultsTable } from '@/components/screening/ResultsTable'
import { ExportPanel } from '@/components/export/ExportPanel'
import { useProjects } from '@/hooks/useProjects'
import { api } from '@/lib/api'

function formatTime(iso: string) {
  return (
    new Date(iso).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
    }) + ' UTC'
  )
}

export function ScreeningResultsPage() {
  const { projectId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const runId = searchParams.get('run_id')

  const { data: projects } = useProjects()
  const project = projects?.find(p => p.id === projectId)

  const { data: runs } = useScreeningRuns(projectId)
  const { data: criteriaHistory } = useCriteriaHistory(projectId)

  // Target run: explicit run_id param, or latest completed
  const targetRun = runId
    ? runs?.find(r => r.id === runId)
    : runs
        ?.filter(r => r.status === 'completed')
        .sort(
          (a, b) =>
            new Date(b.completed_at ?? 0).getTime() - new Date(a.completed_at ?? 0).getTime(),
        )[0]

  const criteriaVersion = criteriaHistory?.find(c => c.id === targetRun?.criteria_id)?.version

  const resumeMutation = useMutation({
    mutationFn: () => api.screening.resume(projectId, targetRun!.id),
    onSuccess: () => {
      navigate(`/projects/${projectId}/screening`)
      qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] })
    },
  })

  // Per-decision counts scoped to the target run
  const runParam = targetRun?.id ? { run_id: targetRun.id } : undefined
  const { data: includeData } = useScreeningResults(projectId, {
    ...runParam,
    decision: 'include',
    page: 1,
    page_size: 1,
  })
  const { data: excludeData } = useScreeningResults(projectId, {
    ...runParam,
    decision: 'exclude',
    page: 1,
    page_size: 1,
  })
  const { data: uncertainData } = useScreeningResults(projectId, {
    ...runParam,
    decision: 'uncertain',
    page: 1,
    page_size: 1,
  })

  const STATS = [
    { label: 'Include', count: includeData?.total, colour: '#27500A' },
    { label: 'Exclude', count: excludeData?.total, colour: '#791F1F' },
    { label: 'Uncertain', count: uncertainData?.total, colour: '#633806' },
  ]

  const isCancelled = targetRun?.status === 'cancelled'
  const hasActiveRun = runs?.some(r => r.status === 'running' || r.status === 'pending')
  const stageLabel =
    targetRun?.stage === 'abstract' ? 'Abstract screening' : 'Full-text screening'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Page header */}
      <div style={{ padding: '20px 24px 0' }}>
        <p
          style={{
            fontSize: 15,
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            margin: '0 0 2px',
          }}
        >
          Screening results{targetRun && ` — ${stageLabel}`}
        </p>
        {targetRun && (
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
            {isCancelled
              ? `Paused · ${targetRun.screened_count ?? 0} / ${targetRun.total_articles} articles screened`
              : targetRun.completed_at
                ? `Completed ${formatTime(targetRun.completed_at)} · ${targetRun.total_articles.toLocaleString()} articles`
                : null}
            {criteriaVersion != null && ` · Criteria v${criteriaVersion}`}
          </p>
        )}
      </div>

      {/* Cancelled run banner */}
      {isCancelled && !hasActiveRun && (
        <div
          style={{
            background: '#FAEEDA',
            border: '0.5px solid #633806',
            borderRadius: 'var(--border-radius-md)',
            padding: '12px 16px',
            margin: '16px 24px 0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <p style={{ fontSize: 13, fontWeight: 500, color: '#633806', margin: 0 }}>
              This screening run was paused
            </p>
            <p style={{ fontSize: 12, color: '#633806', marginTop: 2, marginBottom: 0 }}>
              {targetRun.screened_count ?? 0} of {targetRun.total_articles} articles were
              screened before stopping. Remaining{' '}
              {targetRun.total_articles - (targetRun.screened_count ?? 0)} articles have no
              decision.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0, marginLeft: 16 }}>
            <button
              onClick={() => resumeMutation.mutate()}
              disabled={resumeMutation.isPending}
              style={{
                fontSize: 13,
                background: 'var(--color-text-primary)',
                color: 'var(--color-background-primary)',
                border: 'none',
                padding: '6px 14px',
                borderRadius: 'var(--border-radius-md)',
                cursor: 'pointer',
              }}
            >
              Resume screening →
            </button>
            <button
              onClick={() => navigate(`/projects/${projectId}/screening`)}
              style={{
                fontSize: 13,
                background: 'transparent',
                border: '0.5px solid var(--color-border-secondary)',
                padding: '6px 14px',
                borderRadius: 'var(--border-radius-md)',
                cursor: 'pointer',
                color: 'var(--color-text-primary)',
              }}
            >
              Start fresh
            </button>
          </div>
        </div>
      )}

      {/* Two-column body */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          flex: 1,
          padding: '20px 24px',
          alignItems: 'flex-start',
        }}
      >
        {/* Left sidebar — summary + export */}
        <div style={{ width: 160, flexShrink: 0, marginRight: 24 }}>
          {STATS.map(({ label, count, colour }) => (
            <div key={label} style={{ marginBottom: 14 }}>
              <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '0 0 2px' }}>
                {label}
              </p>
              <p style={{ fontSize: 22, fontWeight: 500, color: colour, margin: 0 }}>
                {count != null ? count.toLocaleString() : '—'}
              </p>
            </div>
          ))}

          <hr
            style={{
              border: 'none',
              borderTop: '0.5px solid var(--color-border-tertiary)',
              margin: '16px 0',
            }}
          />

          <ExportPanel projectId={projectId} projectName={project?.name} />
        </div>

        {/* Right — results table */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <ResultsTable projectId={projectId} runId={targetRun?.id} />
        </div>
      </div>
    </div>
  )
}
