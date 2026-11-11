interface StatCardProps {
  label: string
  value?: number | string
  subtitle?: string
}

export function StatCard({ label, value, subtitle }: StatCardProps) {
  return (
    <div style={{
      background: 'var(--color-background-secondary)',
      borderRadius: 'var(--border-radius-md)',
      padding: 16,
    }}>
      <p style={{
        fontSize: 12,
        color: 'var(--color-text-secondary)',
        marginBottom: 6,
      }}>
        {label}
      </p>
      {value === undefined ? (
        <div style={{
          height: 34,
          width: 60,
          background: 'var(--color-border-tertiary)',
          borderRadius: 4,
          marginBottom: subtitle ? 6 : 0,
        }} />
      ) : (
        <p style={{
          fontSize: 28,
          fontWeight: 500,
          color: 'var(--color-text-primary)',
          lineHeight: 1,
          marginBottom: subtitle ? 6 : 0,
        }}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </p>
      )}
      {subtitle && (
        <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
          {subtitle}
        </p>
      )}
    </div>
  )
}
