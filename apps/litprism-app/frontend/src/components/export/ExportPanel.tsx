import { useState } from 'react'
import { api } from '@/lib/api'

interface ExportGroup {
  heading: string
  note?: string
  formats: { label: string; format: string; ext: string }[]
}

const EXPORT_GROUPS: ExportGroup[] = [
  {
    heading: 'Reference files',
    formats: [
      { label: 'RIS',  format: 'ris',  ext: 'ris'  },
      { label: 'NBIB', format: 'nbib', ext: 'nbib' },
      { label: 'CSV',  format: 'csv',  ext: 'csv'  },
      { label: 'JSON', format: 'json', ext: 'json' },
    ],
  },
  {
    heading: 'Screening-ready',
    note: 'Includes include/exclude labels for active learning',
    formats: [
      { label: 'ASReview format', format: 'asreview', ext: 'xlsx' },
    ],
  },
  {
    heading: 'Reporting',
    note: 'Search strategy, filters, dates for all sources',
    formats: [
      { label: 'PRISMA-S supplementary table (.docx)', format: 'prisma-s', ext: 'docx' },
    ],
  },
]

interface ExportPanelProps {
  projectId: string
  projectName?: string
}

export function ExportPanel({ projectId, projectName = 'results' }: ExportPanelProps) {
  const [loading, setLoading] = useState<string | null>(null)

  async function handleDownload(format: string, ext: string) {
    if (loading) return
    setLoading(format)
    try {
      const blob = await api.export_.download(projectId, format)
      const slug = (projectName || 'litprism').toLowerCase().replace(/\s+/g, '-')
      const filename = `litprism-${slug}-${format}.${ext}`
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
        Export results
      </p>

      {EXPORT_GROUPS.map(group => (
        <div key={group.heading}>
          <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)', marginBottom: 8 }}>
            {group.heading}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: group.note ? 6 : 0 }}>
            {group.formats.map(({ label, format, ext }) => (
              <button
                key={format}
                onClick={() => handleDownload(format, ext)}
                disabled={loading === format}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: 12,
                  padding: '5px 12px',
                  borderRadius: 6,
                  border: '0.5px solid var(--color-border-tertiary)',
                  background: loading === format ? 'var(--color-background-secondary)' : 'var(--color-background-primary)',
                  color: 'var(--color-text-primary)',
                  cursor: loading === format ? 'default' : 'pointer',
                  opacity: loading === format ? 0.6 : 1,
                }}
              >
                <span style={{ fontSize: 11 }}>↓</span>
                {loading === format ? 'Downloading…' : label}
              </button>
            ))}
          </div>
          {group.note && (
            <p style={{ fontSize: 11, color: 'var(--color-text-secondary)', margin: 0 }}>
              {group.note}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
