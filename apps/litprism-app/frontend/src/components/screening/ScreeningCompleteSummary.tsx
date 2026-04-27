import { useNavigate } from 'react-router-dom'
import type { ScreeningRunOut } from '@/lib/types'

interface Props {
  projectId: string
  run: ScreeningRunOut
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return ''
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime()
  const minutes = Math.round(ms / 60000)
  return `${minutes} minute${minutes !== 1 ? 's' : ''}`
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

export function ScreeningCompleteSummary({ projectId, run }: Props) {
  const navigate = useNavigate()
  const total = run.total_articles
  const duration = formatDuration(run.started_at, run.completed_at)

  function pct(n: number) {
    return total > 0 ? `${Math.round((n / total) * 100)}%` : '—'
  }

  return (
    <div style={{ padding: '24px', maxWidth: '600px' }}>
      <p style={{ fontSize: '15px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
        ✓ Screening complete
      </p>
      {run.completed_at && (
        <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
          Finished {formatTime(run.completed_at)}
          {duration && ` · ${total.toLocaleString()} articles in ${duration}`}
        </p>
      )}

      <div style={{ marginBottom: '20px' }}>
        {[
          { label: 'Screened', count: run.screened_count },
          { label: 'Errors', count: run.error_count },
        ].map(({ label, count }) => (
          <div
            key={label}
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: '10px',
              padding: '6px 0',
              borderBottom: '0.5px solid var(--color-border-tertiary)',
              fontSize: '13px',
            }}
          >
            <span style={{ width: '80px', color: 'var(--color-text-secondary)' }}>{label}</span>
            <span style={{ width: '50px', fontWeight: 500, color: 'var(--color-text-primary)', textAlign: 'right' }}>
              {count.toLocaleString()}
            </span>
            <span style={{ width: '40px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
              ({pct(count)})
            </span>
          </div>
        ))}
      </div>

      <button
        onClick={() => navigate(`/projects/${projectId}/screening/results`)}
        style={{
          fontSize: '13px',
          fontWeight: 500,
          padding: '8px 18px',
          background: 'var(--color-text-primary)',
          color: 'var(--color-background-primary)',
          border: 'none',
          borderRadius: 'var(--border-radius-md)',
          cursor: 'pointer',
        }}
      >
        View results →
      </button>
    </div>
  )
}
