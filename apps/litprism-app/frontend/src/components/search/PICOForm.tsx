interface PICOValues {
  population: string
  intervention: string
  comparator: string
  outcome: string
}

interface PICOFormProps {
  values: PICOValues
  onChange: (values: PICOValues) => void
}

export function PICOForm({ values, onChange }: PICOFormProps) {
  const set = (field: keyof PICOValues) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...values, [field]: e.target.value })

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Population</label>
        <input
          type="text"
          value={values.population}
          onChange={set('population')}
          placeholder="e.g. Crohn disease, IBD"
          style={{ fontSize: '13px' }}
        />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Intervention</label>
        <input
          type="text"
          value={values.intervention}
          onChange={set('intervention')}
          placeholder="e.g. probiotic, Lactobacillus"
          style={{ fontSize: '13px' }}
        />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
          Comparator{' '}
          <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>optional</span>
        </label>
        <input
          type="text"
          value={values.comparator}
          onChange={set('comparator')}
          placeholder="e.g. placebo"
          style={{ fontSize: '13px' }}
        />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
          Outcome{' '}
          <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>optional</span>
        </label>
        <input
          type="text"
          value={values.outcome}
          onChange={set('outcome')}
          placeholder="e.g. remission"
          style={{ fontSize: '13px' }}
        />
      </div>
    </div>
  )
}
