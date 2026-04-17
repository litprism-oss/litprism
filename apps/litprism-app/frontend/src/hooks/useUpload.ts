import type { UploadRecordOut } from '@/lib/types'

// Stub — implemented in Session 9.2
export function useUploads(_projectId: string): { data: UploadRecordOut[] | undefined; isLoading: boolean } {
  return { data: undefined, isLoading: false }
}

export function useUploadFile() {
  return { mutate: () => {}, mutateAsync: async () => {}, isPending: false }
}
