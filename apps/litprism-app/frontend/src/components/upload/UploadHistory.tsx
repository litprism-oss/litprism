import type { UploadRecordOut } from '@/lib/types'
import { formatDate, formatCount } from '@/lib/utils'

interface UploadHistoryProps {
  uploads: UploadRecordOut[]
}

export function UploadHistory({ uploads }: UploadHistoryProps) {
  if (uploads.length === 0) {
    return (
      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
        No uploads yet — drag a file above to get started.
      </p>
    )
  }

  return (
    <div>
      {uploads.map((u) => (
        <div
          key={u.id}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 0',
            borderBottom: '0.5px solid var(--color-border-tertiary)',
          }}
        >
          <span style={{ fontSize: '13px', color: 'var(--color-text-primary)' }}>
            {u.filename}
          </span>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            {u.source_label && (
              <span
                style={{
                  fontSize: '11px',
                  padding: '2px 8px',
                  borderRadius: '99px',
                  background: 'var(--color-background-secondary)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                {u.source_label}
              </span>
            )}
            <span>{formatCount(u.record_count)} records</span>
            <span>{formatDate(u.uploaded_at)}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
