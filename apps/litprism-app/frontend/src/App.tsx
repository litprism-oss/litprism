import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { NewProjectPage } from '@/pages/NewProjectPage'
import { ProjectOverviewPage } from '@/pages/ProjectOverviewPage'
import { SearchPage } from '@/pages/SearchPage'
import { UploadPage } from '@/pages/UploadPage'
import { CriteriaPage } from '@/pages/CriteriaPage'
import { ScreeningPage } from '@/pages/ScreeningPage'
import { ScreeningResultsPage } from '@/pages/ScreeningResultsPage'
import { ExportPage } from '@/pages/ExportPage'
import { PRISMAPage } from '@/pages/PRISMAPage'
import { ArticleListPage } from '@/pages/ArticleListPage'
import { Toaster } from '@/components/ui/sonner'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="projects/new" element={<NewProjectPage />} />
            <Route path="projects/:projectId" element={<ProjectOverviewPage />} />
            <Route path="projects/:projectId/search" element={<SearchPage />} />
            <Route path="projects/:projectId/upload" element={<UploadPage />} />
            <Route path="projects/:projectId/criteria" element={<CriteriaPage />} />
            <Route path="projects/:projectId/screening" element={<ScreeningPage />} />
            <Route path="projects/:projectId/screening/results" element={<ScreeningResultsPage />} />
            <Route path="projects/:projectId/export" element={<ExportPage />} />
            <Route path="projects/:projectId/prisma" element={<PRISMAPage />} />
            <Route path="projects/:projectId/articles" element={<ArticleListPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" />
    </QueryClientProvider>
  )
}
