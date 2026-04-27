import { useParams } from 'react-router-dom'
import { useScreeningRuns } from '@/hooks/useScreening'
import { useScreeningResults } from '@/hooks/useScreeningResults'
import { ResultsTable } from '@/components/screening/ResultsTable'
import { ExportPanel } from '@/components/export/ExportPanel'
import { useProjects } from '@/hooks/useProjects'

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

  const { data: projects } = useProjects()
  const project = projects?.find(p => p.id === projectId)

  const { data: runs } = useScreeningRuns(projectId)
  const completedRun = runs
    ?.filter(r => r.status === 'completed')
    .sort((a, b) => new Date(b.completed_at ?? 0).getTime() - new Date(a.completed_at ?? 0).getTime())[0]

  // Per-decision counts for sidebar summary
  const { data: includeData }   = useScreeningResults(projectId, { decision: 'include',   page: 1, page_size: 1 })
  const { data: excludeData }   = useScreeningResults(projectId, { decision: 'exclude',   page: 1, page_size: 1 })
  const { data: uncertainData } = useScreeningResults(projectId, { decision: 'uncertain', page: 1, page_size: 1 })

  const STATS = [
    { label: 'Include',   count: includeData?.total,   colour: '#27500A' },
    { label: 'Exclude',   count: excludeData?.total,   colour: '#791F1F' },
    { label: 'Uncertain', count: uncertainData?.total, colour: '#633806' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Page header */}
      <div style={{ padding: '20px 24px 0' }}>
        <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 2px' }}>
          Screening results
          {completedRun && ` — ${completedRun.stage === 'abstract' ? 'Abstract' : 'Full-text'} screening`}
        </p>
        {completedRun?.completed_at && (
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
            Completed {formatTime(completedRun.completed_at)}
            {' · '}
            {completedRun.total_articles.toLocaleString()} articles
          </p>
        )}
      </div>

      {/* Two-column body */}
      <div style={{ display: 'flex', gap: 0, flex: 1, padding: '20px 24px', alignItems: 'flex-start' }}>
        {/* Left sidebar — summary + export */}
        <div style={{ width: 160, flexShrink: 0, marginRight: 24 }}>
          {STATS.map(({ label, count, colour }) => (
            <div key={label} style={{ marginBottom: 14 }}>
              <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '0 0 2px' }}>{label}</p>
              <p style={{ fontSize: 22, fontWeight: 500, color: colour, margin: 0 }}>
                {count != null ? count.toLocaleString() : '—'}
              </p>
            </div>
          ))}

          <hr style={{ border: 'none', borderTop: '0.5px solid var(--color-border-tertiary)', margin: '16px 0' }} />

          <ExportPanel projectId={projectId} projectName={project?.name} />
        </div>

        {/* Right — results table */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <ResultsTable projectId={projectId} />
        </div>
      </div>
    </div>
  )
}
