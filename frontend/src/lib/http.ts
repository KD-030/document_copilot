import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

const REQUEST_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  readonly status: number | null
  readonly isNetworkError: boolean

  constructor(
    message: string,
    status: number | null,
    isNetworkError: boolean,
    options?: ErrorOptions,
  ) {
    super(message, options)
    this.name = 'ApiError'
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

function apiUrl(path: string): URL {
  const baseUrl = new URL(`${env.apiBaseUrl}/`)
  const url = new URL(path.replace(/^\/+/, ''), baseUrl)
  if (url.origin !== baseUrl.origin) {
    throw new ApiError('API paths must stay on the configured API origin', null, false)
  }
  return url
}

function errorMessage(payload: unknown, response: Response): string {
  if (typeof payload === 'string' && payload) {
    return payload
  }

  if (payload && typeof payload === 'object') {
    const detail = 'detail' in payload ? payload.detail : undefined
    const message = 'message' in payload ? payload.message : undefined
    if (typeof detail === 'string') return detail
    if (typeof message === 'string') return message
  }

  return response.statusText || `Request failed with status ${response.status}`
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T | undefined> {
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    throw new ApiError('Unable to read the Supabase session', null, false, {
      cause: error,
    })
  }

  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  const timeoutSignal = AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  const signal = init.signal
    ? AbortSignal.any([init.signal, timeoutSignal])
    : timeoutSignal

  let response: Response
  try {
    response = await fetch(apiUrl(path), { ...init, headers, signal })
  } catch (cause) {
    const message =
      cause instanceof DOMException && cause.name === 'TimeoutError'
        ? 'The API request timed out'
        : 'Unable to reach the API'
    throw new ApiError(message, null, true, { cause })
  }

  let responseText: string
  try {
    responseText = await response.text()
  } catch (cause) {
    throw new ApiError('Unable to read the API response', response.status, true, {
      cause,
    })
  }

  if (!response.ok) {
    let payload: unknown = responseText
    try {
      payload = JSON.parse(responseText)
    } catch {
      // Use the raw response text when the API error isn't JSON.
    }
    throw new ApiError(errorMessage(payload, response), response.status, false)
  }

  if (!responseText) return undefined
  try {
    return JSON.parse(responseText) as T
  } catch (cause) {
    throw new ApiError('The API returned invalid JSON', response.status, false, {
      cause,
    })
  }
}

export async function requestStream<T>(
  path: string,
  body: unknown,
  onEvent: (event: T) => void,
): Promise<void> {
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    throw new ApiError('Unable to read the Supabase session', null, false, {
      cause: error,
    })
  }

  const headers = new Headers({
    Accept: 'text/event-stream',
    'Content-Type': 'application/json',
  })
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120_000),
    })
  } catch (cause) {
    const message =
      cause instanceof DOMException && cause.name === 'TimeoutError'
        ? 'The answer request timed out'
        : 'Unable to reach the API'
    throw new ApiError(message, null, true, { cause })
  }

  if (!response.ok) {
    const responseText = await response.text()
    let payload: unknown = responseText
    try {
      payload = JSON.parse(responseText)
    } catch {
      // Use the raw response text when the API error isn't JSON.
    }
    throw new ApiError(errorMessage(payload, response), response.status, false)
  }

  if (!response.body) {
    throw new ApiError('The API returned an empty answer stream', response.status, false)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  function dispatch(frame: string) {
    const dataLines = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
    if (!dataLines.length) return

    let event: unknown
    try {
      event = JSON.parse(dataLines.join('\n'))
    } catch (cause) {
      throw new ApiError('The API returned an invalid answer event', response.status, false, {
        cause,
      })
    }

    if (
      event &&
      typeof event === 'object' &&
      'type' in event &&
      event.type === 'error' &&
      'message' in event &&
      typeof event.message === 'string'
    ) {
      throw new ApiError(event.message, response.status, false)
    }
    onEvent(event as T)
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let frameEnd = /\r?\n\r?\n/.exec(buffer)
      while (frameEnd?.index !== undefined) {
        dispatch(buffer.slice(0, frameEnd.index))
        buffer = buffer.slice(frameEnd.index + frameEnd[0].length)
        frameEnd = /\r?\n\r?\n/.exec(buffer)
      }
      if (done) break
    }
    if (buffer.trim()) dispatch(buffer)
  } catch (cause) {
    await reader.cancel(cause)
    if (cause instanceof ApiError) throw cause
    throw new ApiError('The answer stream was interrupted', response.status, true, {
      cause,
    })
  } finally {
    reader.releaseLock()
  }
}
