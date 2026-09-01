import { useQuery } from '@tanstack/react-query'
import { useCallback } from 'react'
import { useEffect, useState } from 'react'

const key = 'unibrief.ai.model'

export function useModel() {
  const [model, setModel] = useState<string | null>(() => localStorage.getItem(key))
  useEffect(() => { if (model) localStorage.setItem(key, model); else localStorage.removeItem(key) }, [model])
  const update = useCallback((value: string | null) => setModel(value), [])
  return { model, setModel: update }
}

export function useAIDefault() {
  const query = useQuery({ queryKey: ['ai-config'], queryFn: async () => (await fetch('/api/v1/ai/config')).json() as Promise<{ default_model: string; has_api_key: boolean; base_url: string }> })
  return query
}

