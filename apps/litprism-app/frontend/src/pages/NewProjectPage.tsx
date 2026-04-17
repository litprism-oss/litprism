import { useNavigate } from 'react-router-dom'
import { NewProjectForm } from '@/components/projects/NewProjectForm'

export function NewProjectPage() {
  const navigate = useNavigate()

  return (
    <div>
      <button
        onClick={() => navigate('/')}
        style={{
          background: 'transparent',
          border: 'none',
          fontSize: 13,
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
          marginBottom: 20,
          padding: 0,
        }}
      >
        ← Projects
      </button>
      <NewProjectForm />
    </div>
  )
}
