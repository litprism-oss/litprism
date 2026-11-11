interface Step {
  label: string
}

const STEPS: Step[] = [
  { label: 'Search' },
  { label: 'Screen' },
  { label: 'Export' },
]

interface StepIndicatorProps {
  currentStep: 1 | 2 | 3
}

export function StepIndicator({ currentStep }: StepIndicatorProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 28 }}>
      {STEPS.map((step, i) => {
        const stepNum = i + 1
        const isDone = stepNum < currentStep
        const isCurrent = stepNum === currentStep
        const isUpcoming = stepNum > currentStep

        const circleStyle: React.CSSProperties = {
          width: 28,
          height: 28,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 12,
          fontWeight: 500,
          flexShrink: 0,
          background: isUpcoming
            ? 'var(--color-background-secondary)'
            : 'var(--color-text-primary)',
          color: isUpcoming
            ? 'var(--color-text-secondary)'
            : 'var(--color-background-primary)',
          border: isUpcoming ? '0.5px solid var(--color-border-tertiary)' : 'none',
        }

        const labelStyle: React.CSSProperties = {
          fontSize: 13,
          fontWeight: isCurrent || isDone ? 500 : 400,
          color: isUpcoming ? 'var(--color-text-secondary)' : 'var(--color-text-primary)',
        }

        return (
          <div key={step.label} style={{ display: 'flex', alignItems: 'center', flex: i < STEPS.length - 1 ? undefined : 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={circleStyle}>
                {isDone ? '✓' : stepNum}
              </div>
              <span style={labelStyle}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                flex: 1,
                minWidth: 32,
                height: '0.5px',
                margin: '0 12px',
                background: isDone
                  ? 'var(--color-text-primary)'
                  : 'var(--color-border-tertiary)',
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
