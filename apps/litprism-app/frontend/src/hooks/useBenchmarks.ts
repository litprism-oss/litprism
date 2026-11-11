import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useBenchmarks() {
  return useQuery({
    queryKey: ['benchmarks'],
    queryFn: api.benchmarks.list,
    // Poll while any run is in progress.
    refetchInterval: (query) =>
      query.state.data?.some((d) => ['pending', 'running'].includes(d.latest_run?.status ?? ''))
        ? 3000
        : false,
  })
}

export function useStartBenchmark() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (slug: string) => api.benchmarks.start(slug),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['benchmarks'] }),
  })
}
