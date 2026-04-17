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
    </div>
  )
}
