import type { SearchRunOut } from '@/lib/types'

// Stub — implemented in Session 9.2
export function useSearchRuns(_projectId: string): { data: SearchRunOut[] | undefined; isLoading: boolean } {
  return { data: undefined, isLoading: false }
}

export function useSearchRun(_projectId: string, _runId: string): { data: SearchRunOut | undefined; isLoading: boolean } {
  return { data: undefined, isLoading: false }
}

export function useCreateSearchRun() {
  return { mutate: () => {}, mutateAsync: async () => {}, isPending: false }
}

export function useUpdateSearchRun() {
  return { mutate: () => {}, mutateAsync: async () => {}, isPending: false }
}

export function useExecuteSearch() {
  return { mutate: () => {}, mutateAsync: async () => {}, isPending: false }
}

export function useSearchPreview() {
  return { mutate: () => {}, mutateAsync: async () => {}, isPending: false }
}
