const FILES = [
  { file: 'records.ris', label: 'Records (.ris)', note: 'Upload this first' },
  { file: 'criteria.json', label: 'Criteria (.json)', note: 'Copy into the Criteria step' },
  { file: 'labels.csv', label: 'Labels (.csv)', note: 'For "Check labels"' },
  { file: 'records.csv', label: 'Records + labels (.csv)', note: 'For the benchmark' },
]

/** Synthetic practice review, served from /samples, so anyone can try the whole flow. */
export function SampleData() {
  return (
    <div
      style={{
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        padding: 16,
      }}
    >
      <p style={{ fontSize: 14, fontWeight: 500, margin: '0 0 4px' }}>No data? Try the sample review</p>
      <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: '0 0 12px' }}>
        65 invented records about probiotics in Crohn&apos;s disease, with known answers (25 relevant). Not real
        publications; for testing only. Upload the .ris, screen it with the criteria, then compare with the labels.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {FILES.map(({ file, label, note }) => (
          <a
            key={file}
            href={`/samples/${file}`}
            download
            style={{
              minHeight: 44,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              padding: '0 14px',
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 'var(--border-radius-md)',
              color: 'var(--color-text-primary)',
              textDecoration: 'none',
              fontSize: 13,
            }}
          >
            <span>↓ {label}</span>
            <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{note}</span>
          </a>
        ))}
      </div>
    </div>
  )
}
