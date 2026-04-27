import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useCriteria, useCriteriaHistory, useCreateCriteria } from '@/hooks/useCriteria'
import { CriterionList } from '@/components/criteria/CriterionList'
import { CriteriaVersionHistory } from '@/components/criteria/CriteriaVersionHistory'

export function CriteriaPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const pid = projectId ?? ''

  const { data: active } = useCriteria(pid)
  const { data: history } = useCriteriaHistory(pid)
  const createCriteria = useCreateCriteria(pid)

  const [inclusion, setInclusion] = useState<string[]>([])
  const [exclusion, setExclusion] = useState<string[]>([])
  const [isDirty, setIsDirty] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  // Pre-fill from active criteria on load
  useEffect(() => {
    if (active) {
      setInclusion(active.inclusion)
      setExclusion(active.exclusion)
      setIsDirty(false)
    }
  }, [active?.id])

  // Warn on navigation away with unsaved changes
  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  function handleInclusionChange(items: string[]) {
    setInclusion(items)
    setIsDirty(true)
  }

  function handleExclusionChange(items: string[]) {
    setExclusion(items)
    setIsDirty(true)
  }

  async function handleSave() {
    const cleanInclusion = inclusion.map((s) => s.trim()).filter(Boolean)
    const cleanExclusion = exclusion.map((s) => s.trim()).filter(Boolean)
    try {
      await createCriteria.mutateAsync({ inclusion: cleanInclusion, exclusion: cleanExclusion })
      setInclusion(cleanInclusion)
      setExclusion(cleanExclusion)
      setIsDirty(false)
      setToast('Criteria saved — new version created.')
      setTimeout(() => setToast(null), 3000)
    } catch (err) {
      setToast(err instanceof Error ? err.message : 'Failed to save criteria.')
      setTimeout(() => setToast(null), 4000)
    }
  }

  const cleanInclusion = inclusion.map((s) => s.trim()).filter(Boolean)
  const saveDisabled = cleanInclusion.length === 0 || !isDirty || createCriteria.isPending

  return (
    <div style={{ padding: '24px 32px', maxWidth: 680, position: 'relative' }}>
      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: 'var(--color-text-primary)',
            color: 'var(--color-background-primary)',
            fontSize: '13px',
            padding: '10px 16px',
            borderRadius: 'var(--border-radius-md)',
            zIndex: 1000,
          }}
        >
          {toast}
        </div>
      )}

      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px',
        }}
      >
        <span
          style={{
            fontSize: '16px',
            fontWeight: 500,
            color: 'var(--color-text-primary)',
          }}
        >
          Eligibility criteria
        </span>
        <button
          onClick={handleSave}
          disabled={saveDisabled}
          style={{
            background: saveDisabled ? 'var(--color-border-tertiary)' : 'var(--color-text-primary)',
            color: saveDisabled
              ? 'var(--color-text-tertiary)'
              : 'var(--color-background-primary)',
            border: 'none',
            padding: '7px 16px',
            borderRadius: 'var(--border-radius-md)',
            fontSize: '13px',
            cursor: saveDisabled ? 'not-allowed' : 'pointer',
          }}
        >
          {createCriteria.isPending ? 'Saving…' : 'Save criteria'}
        </button>
      </div>

      <p
        style={{
          fontSize: '12px',
          color: 'var(--color-text-secondary)',
          marginBottom: '20px',
        }}
      >
        Saving creates a new version — previous versions are preserved in the history below.
      </p>

      <CriterionList
        label="Inclusion criteria"
        items={inclusion}
        onChange={handleInclusionChange}
        type="inclusion"
      />

      <CriterionList
        label="Exclusion criteria"
        items={exclusion}
        onChange={handleExclusionChange}
        type="exclusion"
      />

      <CriteriaVersionHistory versions={history ?? []} />
    </div>
  )
}
