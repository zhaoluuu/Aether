import { describe, expect, it } from 'vitest'

import { buildUsageStatusUrl } from '@/utils/url'

describe('url helpers', () => {
  it('appends /v1/usage for regular base urls', () => {
    expect(buildUsageStatusUrl('{{baseUrl}}')).toBe('{{baseUrl}}/v1/usage')
    expect(buildUsageStatusUrl('https://gateway.example.com/api')).toBe(
      'https://gateway.example.com/api/v1/usage',
    )
  })

  it('avoids duplicating /v1 when base url already includes it', () => {
    expect(buildUsageStatusUrl('https://gateway.example.com/v1', '{{baseUrl}}')).toBe(
      '{{baseUrl}}/usage',
    )
    expect(buildUsageStatusUrl('https://gateway.example.com/v1/')).toBe(
      'https://gateway.example.com/v1/usage',
    )
  })

  it('falls back to the public usage route when base url is empty', () => {
    expect(buildUsageStatusUrl('')).toBe('/v1/usage')
  })
})
