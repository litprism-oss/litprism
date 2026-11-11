import { Link } from 'react-router-dom'
import { useProjects } from '@/hooks/useProjects'
import { ProjectGrid } from '@/components/projects/ProjectGrid'

export function DashboardPage() {
  const { data: projects, isLoading } = useProjects()

  return (
    <div>
      <p style={{
        fontSize: 18,
        fontWeight: 500,
        color: 'var(--color-text-primary)',
        marginBottom: 20,
      }}>
        Your Reviews
      </p>
      <ProjectGrid
        projects={projects ?? []}
        isLoading={isLoading}
      />
      <Link
        to="/benchmarks"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          minHeight: 44,
          marginTop: 20,
          padding: '0 16px',
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 'var(--border-radius-lg)',
          color: 'var(--color-text-primary)',
          textDecoration: 'none',
          fontSize: 14,
        }}
      >
        <span>Try a benchmark: how well does the AI screen?</span>
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  )
}
