import { useNavigate } from 'react-router-dom'
import { ProjectCard } from '@/components/projects/ProjectCard'
import type { ProjectOut, SearchRunOut } from '@/lib/types'

interface ProjectGridProps {
  projects: ProjectOut[]
  latestRuns?: Record<string, SearchRunOut>
  isLoading: boolean
}

export function ProjectGrid({ projects, latestRuns, isLoading }: ProjectGridProps) {
  const navigate = useNavigate()

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: 16,
  }

  if (isLoading) {
    return (
      <div style={gridStyle}>
        {[0, 1, 2].map((i) => (
          <ProjectCard key={i} isLoading />
        ))}
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '64px 0',
        gap: 12,
      }}>
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          No reviews yet
        </p>
        <button
          onClick={() => navigate('/projects/new')}
          style={{
            background: 'var(--color-text-primary)',
            color: 'var(--color-background-primary)',
            border: 'none',
            padding: '8px 18px',
            borderRadius: 'var(--border-radius-md)',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Create your first review
        </button>
      </div>
    )
  }

  return (
    <div style={gridStyle}>
      {projects.map((project) => (
        <ProjectCard
          key={project.id}
          project={project}
          latestRun={latestRuns?.[project.id]}
        />
      ))}
    </div>
  )
}
