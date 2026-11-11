import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-US')
}

export function translateQuery(
  query: string,
  source: 'europepmc' | 'scopus' | 'wos' | 'embase',
): string {
  switch (source) {
    case 'europepmc': {
      let q = query
      q = q.replace(/"([^"]+)"\[MeSH(?:[^\]]*)\]/g, 'MESH:"$1"')
      q = q.replace(/(\S+)\[tiab\]/g, '$1')
      q = q.replace(/(\S+)\[ti\]/g, 'TITLE:$1')
      q = q.replace(/(\S+)\[ab\]/g, 'ABSTRACT:$1')
      q = q.replace(/(\S+)\[au\]/g, 'AUTH:"$1"')
      return q.trim()
    }
    case 'scopus': {
      let q = query
      q = q.replace(/"([^"]+)"\[MeSH(?:[^\]]*)\]/g, '"$1"')
      q = q.replace(/\[\w+\]/g, '')
      q = q.replace(/\s+/g, ' ').trim()
      return `TITLE-ABS-KEY(${q})`
    }
    case 'wos': {
      let q = query
      q = q.replace(/"([^"]+)"\[MeSH(?:[^\]]*)\]/g, '"$1"')
      q = q.replace(/\[\w+\]/g, '')
      q = q.replace(/\s+/g, ' ').trim()
      return `TS=(${q})`
    }
    case 'embase': {
      let q = query
      q = q.replace(/"([^"]+)"\[MeSH(?:[^\]]*)\]/g, "'$1'/exp")
      q = q.replace(/\[\w+\]/g, '')
      q = q.replace(/\s+/g, ' ').trim()
      return q
    }
  }
}
