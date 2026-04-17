import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useUploadFile, useUploads } from '@/hooks/useUpload'
import { UploadDropzone } from '@/components/upload/UploadDropzone'
import { UploadHistory } from '@/components/upload/UploadHistory'
import { formatCount } from '@/lib/utils'

const SOURCE_OPTIONS = [
  'PubMed (web interface)',
  'Scopus',
  'Web of Science',
  'Embase',
  'Cochrane Library',
  'CINAHL',
  'PsycINFO',
  'ClinicalTrials.gov',
  'Manual search',
  'Other',
]

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export function UploadPage() {
  const { projectId = '' } = useParams()
  const fileRef = useRef<File | null>(null)

  const [sourceLabel, setSourceLabel] = useState(SOURCE_OPTIONS[0])
  const [searchDate, setSearchDate] = useState(todayISO())
  const [searchStrategy, setSearchStrategy] = useState('')
  const [limitsApplied, setLimitsApplied] = useState('')

  const uploadFile = useUploadFile(projectId)
  const { data: uploads = [] } = useUploads(projectId)

  const handleUpload = () => {
    const file = fileRef.current
    if (!file) {
      toast.error('Please select a file first')
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    if (sourceLabel) formData.append('source_label', sourceLabel)
    if (searchDate) formData.append('search_date', searchDate)
    if (searchStrategy.trim()) formData.append('search_strategy_used', searchStrategy.trim())
    if (limitsApplied.trim()) formData.append('limits_applied', limitsApplied.trim())

    uploadFile.mutate(formData, {
      onSuccess: (data) => {
        toast.success(
          `Upload complete — Parsed: ${formatCount(data.total_parsed)} · Added: ${formatCount(data.new_articles)} · Duplicates removed: ${formatCount(data.duplicates_found)}`,
        )
        fileRef.current = null
        setSearchStrategy('')
        setLimitsApplied('')
        setSearchDate(todayISO())
      },
      onError: (err) => {
        toast.error(`Upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
      },
    })
  }

  return (
    <div style={{ padding: '24px', maxWidth: '560px' }}>
      <p
        style={{
          fontSize: '14px',
          fontWeight: 500,
          color: 'var(--color-text-primary)',
          marginBottom: '16px',
        }}
      >
        Add references from any database
      </p>

      <UploadDropzone onFile={(f) => { fileRef.current = f }} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          marginBottom: '14px',
        }}
      >
        {/* Source database */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            Source database
          </label>
          <select
            value={sourceLabel}
            onChange={(e) => setSourceLabel(e.target.value)}
            style={{ fontSize: '13px' }}
          >
            {SOURCE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>

        {/* Search date */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            Search date
          </label>
          <input
            type="date"
            value={searchDate}
            onChange={(e) => setSearchDate(e.target.value)}
            style={{ fontSize: '13px' }}
          />
        </div>

        {/* Search strategy */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', gridColumn: '1 / -1' }}>
          <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            Search strategy used{' '}
            <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>optional</span>
          </label>
          <textarea
            value={searchStrategy}
            onChange={(e) => setSearchStrategy(e.target.value)}
            placeholder="Paste the query string you ran..."
            style={{ fontSize: '13px', resize: 'vertical', minHeight: '60px' }}
          />
        </div>

        {/* Limits applied */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', gridColumn: '1 / -1' }}>
          <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            Limits applied{' '}
            <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>optional</span>
          </label>
          <textarea
            value={limitsApplied}
            onChange={(e) => setLimitsApplied(e.target.value)}
            placeholder="Date, language, document type..."
            style={{ fontSize: '13px', resize: 'vertical', minHeight: '44px' }}
          />
        </div>
      </div>

      <button
        onClick={handleUpload}
        disabled={uploadFile.isPending}
        style={{
          background: 'var(--color-text-primary)',
          color: 'var(--color-background-primary)',
          border: 'none',
          padding: '8px 18px',
          borderRadius: 'var(--border-radius-md)',
          fontSize: '13px',
          cursor: uploadFile.isPending ? 'not-allowed' : 'pointer',
          opacity: uploadFile.isPending ? 0.6 : 1,
          marginBottom: '24px',
        }}
      >
        {uploadFile.isPending ? 'Uploading…' : 'Upload'}
      </button>

      {uploads.length > 0 && (
        <>
          <p
            style={{
              fontSize: '12px',
              fontWeight: 500,
              color: 'var(--color-text-secondary)',
              marginBottom: '10px',
            }}
          >
            Previous uploads
          </p>
          <UploadHistory uploads={uploads} />
        </>
      )}
    </div>
  )
}
