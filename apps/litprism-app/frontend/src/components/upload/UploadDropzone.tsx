import { useRef, useState } from 'react'

const ACCEPTED_EXTENSIONS = ['.nbib', '.ris', '.bib', '.csv', '.xlsx', '.pdf']

function getExtension(filename: string): string {
  return '.' + filename.split('.').pop()!.toLowerCase()
}

interface UploadDropzoneProps {
  onFile: (file: File) => void
}

export function UploadDropzone({ onFile }: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const [selected, setSelected] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (file: File | undefined) => {
    if (!file) return
    const ext = getExtension(file.name)
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type "${ext}". Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`)
      setSelected(null)
      return
    }
    setError(null)
    setSelected(file)
    onFile(file)
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div style={{ marginBottom: '18px' }}>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          handleFile(e.dataTransfer.files[0])
        }}
        style={{
          border: `1.5px dashed ${dragging ? 'var(--color-text-primary)' : 'var(--color-border-secondary)'}`,
          borderRadius: 'var(--border-radius-lg)',
          padding: '28px 20px',
          textAlign: 'center',
          background: 'var(--color-background-secondary)',
          cursor: 'pointer',
        }}
      >
        {selected ? (
          <>
            <p style={{ fontSize: '13px', color: 'var(--color-text-primary)', marginBottom: '4px' }}>
              {selected.name}
            </p>
            <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              {formatSize(selected.size)} · Click to change
            </p>
          </>
        ) : (
          <>
            <p style={{ fontSize: '13px', color: 'var(--color-text-primary)', marginBottom: '4px' }}>
              Drop file here or click to browse
            </p>
            <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              {ACCEPTED_EXTENSIONS.join(' · ')}
            </p>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(',')}
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {error && (
        <p style={{ fontSize: '12px', color: '#8B5E00', marginTop: '6px' }}>{error}</p>
      )}
    </div>
  )
}
