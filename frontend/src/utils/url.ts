/**
 * 构建完整的 API URL
 *
 * 用于需要完整 URL 的场景（如 OAuth 重定向），
 * 处理 VITE_API_URL 环境变量和路径拼接。
 */
export function getApiUrl(path: string): string {
  const base = import.meta.env.VITE_API_URL || ''
  // 移除 base 尾部的 `/`，避免拼接成 `//api/...`
  return base ? `${base.replace(/\/$/, '')}${path}` : path
}

/**
 * 构建 CC Switch 用量查询地址。
 *
 * CC Switch 会把导入时的 endpoint 作为 `{{baseUrl}}` 注入脚本。
 * 当 endpoint 本身已经以 `/v1` 结尾时，不能再重复拼接 `/v1/usage`。
 */
export function buildUsageStatusUrl(baseUrl: string, scriptBaseUrl: string = baseUrl): string {
  const normalizedBase = baseUrl.replace(/\/+$/, '')
  const normalizedScriptBase = scriptBaseUrl.replace(/\/+$/, '')

  if (!normalizedBase) {
    return '/v1/usage'
  }

  if (!normalizedScriptBase) {
    return normalizedBase.endsWith('/v1') ? '/usage' : '/v1/usage'
  }

  return normalizedBase.endsWith('/v1')
    ? `${normalizedScriptBase}/usage`
    : `${normalizedScriptBase}/v1/usage`
}
