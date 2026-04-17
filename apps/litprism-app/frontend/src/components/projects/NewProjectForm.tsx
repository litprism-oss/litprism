import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useCreateProject } from '@/hooks/useProjects'
import type { ReviewType } from '@/lib/types'

const REVIEW_TYPE_OPTIONS: { value: ReviewType; label: string }[] = [
  { value: 'systematic',   label: 'Systematic review' },
  { value: 'scoping',      label: 'Scoping review' },
  { value: 'rapid',        label: 'Rapid review' },
  { value: 'literature',   label: 'Literature review' },
  { value: 'state_of_art', label: 'State-of-the-art review' },
]

const PICO_REVIEW_TYPES: ReviewType[] = ['systematic', 'rapid']

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  fontSize: 13,
  border: '0.5px solid var(--color-border-tertiary)',
  borderRadius: 'var(--border-radius-md)',
  background: 'var(--color-background-primary)',
  color: 'var(--color-text-primary)',
  outline: 'none',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  color: 'var(--color-text-secondary)',
  marginBottom: 6,
}

const fieldStyle: React.CSSProperties = {
  marginBottom: 16,
}

export function NewProjectForm() {
  const navigate = useNavigate()
  const { mutateAsync: createProject, isPending } = useCreateProject()

  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [researchQuestion, setResearchQuestion] = useState('')
  const [reviewType, setReviewType] = useState<ReviewType>('systematic')
  const [population, setPopulation] = useState('')
  const [intervention, setIntervention] = useState('')
  const [comparator, setComparator] = useState('')
  const [outcome, setOutcome] = useState('')

  const needsPico = PICO_REVIEW_TYPES.includes(reviewType)

  function handleStep1(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    if (needsPico) {
      setStep(2)
    } else {
      void submit()
    }
  }

  async function submit(skipPico = false) {
    const picoQuery = !skipPico && needsPico && population.trim()
      ? [population, intervention, comparator, outcome]
          .filter(Boolean)
          .join('; ')
      : undefined

    try {
      const project = await createProject({
        name: name.trim(),
        description: researchQuestion.trim() || undefined,
        research_question: researchQuestion.trim() || undefined,
        review_type: reviewType,
        ...(picoQuery ? { research_question: picoQuery } : {}),
      })
      navigate(`/projects/${project.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project')
    }
  }

  return (
    <div style={{
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 'var(--border-radius-lg)',
      padding: 24,
      maxWidth: 480,
    }}>
      {step === 1 && (
        <form onSubmit={handleStep1}>
          <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: 20 }}>
            New review
          </p>

          <div style={fieldStyle}>
            <label style={labelStyle}>
              Name <span style={{ color: '#791F1F' }}>*</span>
            </label>
            <input
              style={inputStyle}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Probiotics in Crohn's disease"
              required
              autoFocus
            />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Research question (optional)</label>
            <textarea
              style={{ ...inputStyle, resize: 'vertical', minHeight: 72 }}
              value={researchQuestion}
              onChange={(e) => setResearchQuestion(e.target.value)}
              placeholder="What is the effect of…"
            />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Review type</label>
            <select
              style={inputStyle}
              value={reviewType}
              onChange={(e) => setReviewType(e.target.value as ReviewType)}
            >
              {REVIEW_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={!name.trim()}
            style={{
              background: name.trim() ? 'var(--color-text-primary)' : 'var(--color-background-secondary)',
              color: name.trim() ? 'var(--color-background-primary)' : 'var(--color-text-tertiary)',
              border: 'none',
              padding: '8px 18px',
              borderRadius: 'var(--border-radius-md)',
              fontSize: 13,
              cursor: name.trim() ? 'pointer' : 'not-allowed',
            }}
          >
            {needsPico ? 'Next →' : 'Create review'}
          </button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={(e) => { e.preventDefault(); void submit() }}>
          <p style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: 4 }}>
            PICO framework
          </p>
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 20 }}>
            LitPrism will build your search query from these fields.
          </p>

          <div style={fieldStyle}>
            <label style={labelStyle}>
              Population <span style={{ color: '#791F1F' }}>*</span>
            </label>
            <input
              style={inputStyle}
              value={population}
              onChange={(e) => setPopulation(e.target.value)}
              placeholder="e.g. adults with Crohn's disease"
              required
              autoFocus
            />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>
              Intervention <span style={{ color: '#791F1F' }}>*</span>
            </label>
            <input
              style={inputStyle}
              value={intervention}
              onChange={(e) => setIntervention(e.target.value)}
              placeholder="e.g. probiotic supplementation"
              required
            />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Comparator (optional)</label>
            <input
              style={inputStyle}
              value={comparator}
              onChange={(e) => setComparator(e.target.value)}
              placeholder="e.g. placebo"
            />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Outcome (optional)</label>
            <input
              style={inputStyle}
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              placeholder="e.g. disease remission"
            />
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              type="submit"
              disabled={!population.trim() || !intervention.trim() || isPending}
              style={{
                background: population.trim() && intervention.trim()
                  ? 'var(--color-text-primary)'
                  : 'var(--color-background-secondary)',
                color: population.trim() && intervention.trim()
                  ? 'var(--color-background-primary)'
                  : 'var(--color-text-tertiary)',
                border: 'none',
                padding: '8px 18px',
                borderRadius: 'var(--border-radius-md)',
                fontSize: 13,
                cursor: population.trim() && intervention.trim() ? 'pointer' : 'not-allowed',
              }}
            >
              {isPending ? 'Creating…' : 'Create review'}
            </button>
            <button
              type="button"
              onClick={() => void submit(true)}
              disabled={isPending}
              style={{
                background: 'transparent',
                border: '0.5px solid var(--color-border-secondary)',
                color: 'var(--color-text-primary)',
                padding: '8px 16px',
                borderRadius: 'var(--border-radius-md)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Skip — I'll enter my own query
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
