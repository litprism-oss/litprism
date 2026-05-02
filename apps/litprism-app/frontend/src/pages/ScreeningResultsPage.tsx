import { useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useScreeningRuns } from '@/hooks/useScreening'
import { useScreeningResults } from '@/hooks/useScreeningResults'
import { useCriteriaHistory } from '@/hooks/useCriteria'
import { ResultsTable } from '@/components/screening/ResultsTable'
import { ExportPanel } from '@/components/export/ExportPanel'
import { useProjects } from '@/hooks/useProjects'
import { api } from '@/lib/api'
import type { ScreeningDecision } from '@/lib/types'

type FilterTab = 'all' | ScreeningDecision

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
  const [activeTab, setActiveTab] = useState<FilterTab>('all')

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

  const fulltextMutation = useMutation({
    mutationFn: () => api.fulltext.trigger(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fulltextStatus', projectId] }),
  })

  const fulltextScreeningMutation = useMutation({
    mutationFn: () => api.screening.startFulltext(projectId, { stage: 'fulltext', chunk_size: 50 }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] })
      navigate(`/projects/${projectId}/screening?run_id=${data.id}`)
    },
  })

  const { data: fulltextStatus } = useQuery({
    queryKey: ['fulltextStatus', projectId],
    queryFn: () => api.fulltext.status(projectId),
    enabled: activeTab === 'uncertain',
    refetchInterval: (query) =>
      (query.state.data?.pending ?? 0) > 0 ? 5000 : false,
  })

  const retrievalComplete =
    fulltextStatus !== undefined && fulltextStatus.pending === 0 && fulltextStatus.total > 0

  const { data: eligibility } = useQuery({
    queryKey: ['fulltextEligibility', projectId],
    queryFn: () => api.screening.fulltextEligibility(projectId),
    enabled: activeTab === 'uncertain' && retrievalComplete,
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
  const { data: errorData } = useScreeningResults(projectId, {
    ...runParam,
    decision: 'error',
    page: 1,
    page_size: 1,
  })

  const retryMutation = useMutation({
    mutationFn: () => api.screening.retryFailed(projectId, targetRun!.id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['screeningRuns', projectId] })
      qc.invalidateQueries({ queryKey: ['screeningResults', projectId] })
      navigate(`/projects/${projectId}/screening?run_id=${data.run_id}`)
    },
  })

  const STATS = [
    { label: 'Include',  count: includeData?.total,  colour: '#27500A' },
    { label: 'Exclude',  count: excludeData?.total,  colour: '#791F1F' },
    { label: 'Uncertain', count: uncertainData?.total, colour: '#633806' },
    { label: 'Failed',   count: errorData?.total,    colour: '#791F1F' },
  ]

  const isCancelled = targetRun?.status === 'cancelled' || targetRun?.status === 'paused'
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
          {/* Full-text retrieval banner — shown when uncertain tab is active */}
          {activeTab === 'uncertain' && (
            <div
              style={{
                background: '#FAEEDA',
                border: '0.5px solid #633806',
                borderRadius: 'var(--border-radius-md)',
                padding: '12px 16px',
                marginBottom: 16,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                {fulltextStatus && fulltextStatus.pending > 0 ? (
                  <>
                    <p style={{ fontSize: 13, fontWeight: 500, color: '#633806', margin: 0 }}>
                      Retrieving full text… ({fulltextStatus.pending} remaining)
                    </p>
                    <p style={{ fontSize: 12, color: '#633806', marginTop: 2, marginBottom: 0 }}>
                      {fulltextStatus.retrieved} retrieved · {fulltextStatus.unavailable} unavailable · {fulltextStatus.error} errors
                      {' '}out of {fulltextStatus.total} total
                    </p>
                    <p style={{ fontSize: 12, color: '#633806', marginTop: 4, marginBottom: 0 }}>
                      Articles without full text will remain uncertain and need manual review.
                    </p>
                  </>
                ) : retrievalComplete && (eligibility?.eligible ?? 0) > 0 ? (
                  <>
                    <p style={{ fontSize: 13, fontWeight: 500, color: '#633806', margin: 0 }}>
                      {eligibility!.eligible} article{eligibility!.eligible !== 1 ? 's' : ''} ready
                      for full-text screening
                    </p>
                    <p style={{ fontSize: 12, color: '#633806', marginTop: 2, marginBottom: 0 }}>
                      {eligibility!.unavailable > 0 &&
                        `${eligibility!.unavailable} articles unavailable — manual review needed. `}
                      Full text retrieved for {eligibility!.retrieved} articles.
                    </p>
                  </>
                ) : retrievalComplete ? (
                  <>
                    <p style={{ fontSize: 13, fontWeight: 500, color: '#633806', margin: 0 }}>
                      Full text retrieval complete
                    </p>
                    <p style={{ fontSize: 12, color: '#633806', marginTop: 2, marginBottom: 0 }}>
                      {fulltextStatus!.retrieved} retrieved · {fulltextStatus!.unavailable}{' '}
                      unavailable
                      {fulltextStatus!.error > 0 ? ` · ${fulltextStatus!.error} errors` : ''}
                    </p>
                  </>
                ) : (
                  <>
                    <p style={{ fontSize: 13, fontWeight: 500, color: '#633806', margin: 0 }}>
                      {uncertainData?.total ?? 0} articles need full-text review
                    </p>
                    <p style={{ fontSize: 12, color: '#633806', marginTop: 2, marginBottom: 0 }}>
                      Retrieve full text automatically where available (PMC, Unpaywall)
                    </p>
                  </>
                )}
              </div>
              {retrievalComplete && (eligibility?.eligible ?? 0) > 0 ? (
                <button
                  onClick={() => fulltextScreeningMutation.mutate()}
                  disabled={fulltextScreeningMutation.isPending}
                  style={{
                    fontSize: 13,
                    background: 'var(--color-text-primary)',
                    color: 'var(--color-background-primary)',
                    border: 'none',
                    padding: '7px 16px',
                    borderRadius: 'var(--border-radius-md)',
                    cursor: fulltextScreeningMutation.isPending ? 'default' : 'pointer',
                    flexShrink: 0,
                    marginLeft: 16,
                    opacity: fulltextScreeningMutation.isPending ? 0.6 : 1,
                  }}
                >
                  {fulltextScreeningMutation.isPending ? 'Starting…' : 'Run full-text screening →'}
                </button>
              ) : (!fulltextStatus || fulltextStatus.not_attempted > 0) &&
                fulltextStatus?.pending === 0 ? (
                <button
                  onClick={() => fulltextMutation.mutate()}
                  disabled={fulltextMutation.isPending}
                  style={{
                    fontSize: 13,
                    background: 'var(--color-text-primary)',
                    color: 'var(--color-background-primary)',
                    border: 'none',
                    padding: '7px 16px',
                    borderRadius: 'var(--border-radius-md)',
                    cursor: fulltextMutation.isPending ? 'default' : 'pointer',
                    flexShrink: 0,
                    marginLeft: 16,
                    opacity: fulltextMutation.isPending ? 0.6 : 1,
                  }}
                >
                  Retrieve full text →
                </button>
              ) : null}
            </div>
          )}
          {/* Failed screening banner — shown when error tab is active */}
          {activeTab === 'error' && (errorData?.total ?? 0) > 0 && (
            <div
              style={{
                background: '#FDECEA',
                border: '0.5px solid #791F1F',
                borderRadius: 'var(--border-radius-md)',
                padding: '12px 16px',
                marginBottom: 16,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <p style={{ fontSize: 13, fontWeight: 500, color: '#791F1F', margin: 0 }}>
                  {errorData!.total} article{errorData!.total !== 1 ? 's' : ''} failed screening
                </p>
                <p style={{ fontSize: 12, color: '#791F1F', marginTop: 2, marginBottom: 0 }}>
                  Likely caused by rate limits. Retry to re-screen these articles.
                </p>
              </div>
              <button
                onClick={() => retryMutation.mutate()}
                disabled={retryMutation.isPending}
                style={{
                  fontSize: 13,
                  background: '#791F1F',
                  color: '#fff',
                  border: 'none',
                  padding: '7px 16px',
                  borderRadius: 'var(--border-radius-md)',
                  cursor: retryMutation.isPending ? 'default' : 'pointer',
                  flexShrink: 0,
                  marginLeft: 16,
                  opacity: retryMutation.isPending ? 0.6 : 1,
                }}
              >
                {retryMutation.isPending ? 'Retrying…' : 'Retry failed →'}
              </button>
            </div>
          )}
          <ResultsTable
            projectId={projectId}
            runId={targetRun?.id}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        </div>
      </div>
    </div>
  )
}
