import { describe, expect, it } from 'vitest'
import { queryString } from '../api/client'
import { shanghai } from '../utils/format'

describe('API query serialization', () => {
  it('keeps arrays, skips empty values, and preserves order', () => {
    expect(queryString({ keyword: '数据库', page: 2, empty: undefined, tags: [3, 1] })).toBe(
      '?keyword=%E6%95%B0%E6%8D%AE%E5%BA%93&page=2&tags=3&tags=1',
    )
  })
})

describe('Asia/Shanghai presentation', () => {
  it('renders UTC timestamps in the local campus timezone', () => {
    expect(shanghai('2026-09-01T16:00:00Z')).toContain('2026/09/02')
    expect(shanghai(null)).toBe('—')
  })
})

