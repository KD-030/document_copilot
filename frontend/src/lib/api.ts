import { request, requestStream } from '@/lib/http'

export { ApiError } from '@/lib/http'

function jsonRequest<T>(
  method: 'POST' | 'PUT' | 'PATCH',
  path: string,
  body?: unknown,
): Promise<T | undefined> {
  const hasBody = body !== undefined
  return request<T>(path, {
    method,
    ...(hasBody
      ? {
          body: JSON.stringify(body),
          headers: { 'Content-Type': 'application/json' },
        }
      : {}),
  })
}

export const api = {
  get: <T = unknown>(path: string) => request<T>(path),
  post: <T = unknown>(path: string, body?: unknown) =>
    jsonRequest<T>('POST', path, body),
  put: <T = unknown>(path: string, body?: unknown) =>
    jsonRequest<T>('PUT', path, body),
  patch: <T = unknown>(path: string, body?: unknown) =>
    jsonRequest<T>('PATCH', path, body),
  delete: <T = unknown>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
  stream: <T = unknown>(
    path: string,
    body: unknown,
    onEvent: (event: T) => void,
  ) => requestStream<T>(path, body, onEvent),
}
