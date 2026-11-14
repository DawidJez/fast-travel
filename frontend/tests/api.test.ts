import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_URL, ApiError, PARSE_TEXT_MAX_LENGTH, api, errorMessage, errorText, request } from '../src/api/client'

function mockFetch(response: Response | Error) {
  const fn = vi.fn(async () => {
    if (response instanceof Error) throw response
    return response.clone() // a body can be read only once
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('expected the promise to reject')
}

afterEach(() => vi.unstubAllGlobals())

describe('API_URL', () => {
  it('defaults to the local backend without a trailing slash', () => {
    expect(API_URL).toBe('http://127.0.0.1:8000/api')
  })
})

describe('errorMessage', () => {
  it('translates PlaceNotFoundError (single quotes)', () => {
    expect(errorMessage(422, { detail: "Place not found: 'Xyzabc'" })).toBe(
      'Nie znaleziono miejsca „Xyzabc”. Sprawdź pisownię lub podaj dokładniejszą nazwę.',
    )
  })

  it('translates PlaceNotFoundError (double quotes, apostrophe in name)', () => {
    expect(errorMessage(422, { detail: `Place not found: "Pod'górze"` })).toContain('„Pod\'górze”')
  })

  it('describes validation errors per field', () => {
    const detail = [
      { loc: ['body', 'name'], type: 'string_too_short', msg: 'too short' },
      { loc: ['body', 'origin'], type: 'missing', msg: 'Field required' },
      { loc: ['body', 'notes'], type: 'string_too_long', msg: 'too long', ctx: { max_length: 1000 } },
    ]
    expect(errorMessage(422, { detail })).toBe(
      'Nazwa: pole jest wymagane; Skąd: pole jest wymagane; Notatki: za długie (maks. 1000 znaków)',
    )
  })

  it('falls back to the raw message for unknown validation types and fields', () => {
    const detail = [{ loc: ['path', 'trip_id'], type: 'greater_than_equal', msg: 'Input should be >= 1' }]
    expect(errorMessage(422, { detail })).toBe('trip_id: Input should be >= 1')
  })

  it.each([
    [404, { detail: 'Trip 7 not found' }, 'Nie znaleziono podróży (mogła zostać usunięta).'],
    [503, { detail: 'Open-Meteo is unreachable: boom' }, 'Wyszukiwanie miejsc jest chwilowo niedostępne. Spróbuj ponownie za chwilę.'],
    [422, null, 'Nieprawidłowe dane.'],
    [500, null, 'Błąd serwera (HTTP 500).'],
  ])('status %i -> readable message', (status, body, message) => {
    expect(errorMessage(status, body)).toBe(message)
  })
})

describe('request', () => {
  it('returns parsed JSON and calls API_URL + path', async () => {
    const fetchFn = mockFetch(json(200, [{ id: 1 }]))
    await expect(request('/trips')).resolves.toEqual([{ id: 1 }])
    expect(fetchFn).toHaveBeenCalledWith('http://127.0.0.1:8000/api/trips', expect.anything())
  })

  it('sets Content-Type only when there is a body', async () => {
    const fetchFn = mockFetch(json(200, {}))
    await request('/trips', { method: 'POST', body: '{}' })
    await request('/trips')
    const headers = fetchFn.mock.calls.map((call) => (call as unknown[])[1] as RequestInit).map((i) => new Headers(i.headers))
    expect(headers[0].get('Content-Type')).toBe('application/json')
    expect(headers[1].get('Content-Type')).toBeNull()
  })

  it('returns undefined for 204', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(request('/trips/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('throws ApiError with a readable message on HTTP errors', async () => {
    mockFetch(json(422, { detail: "Place not found: 'Nigdzie'" }))
    const error = await caught(request('/trips'))
    expect(error.status).toBe(422)
    expect(error.message).toContain('Nie znaleziono miejsca „Nigdzie”')
  })

  it('handles a non-JSON error body', async () => {
    mockFetch(new Response('<html>Bad Gateway</html>', { status: 502 }))
    const error = await caught(request('/trips'))
    expect(error.message).toBe('Błąd serwera (HTTP 502).')
  })

  it('rejects a non-JSON success body', async () => {
    mockFetch(new Response('oops', { status: 200 }))
    const error = await caught(request('/trips'))
    expect(error.message).toBe('Nieprawidłowa odpowiedź serwera.')
  })

  it('turns a network failure into status 0', async () => {
    mockFetch(new TypeError('Failed to fetch'))
    const error = await caught(request('/trips'))
    expect(error.status).toBe(0)
    expect(error.message).toContain('Brak połączenia z serwerem')
  })
})

describe('api endpoints', () => {
  it.each([
    ['listTrips', () => api.listTrips(), '/trips', 'GET', undefined],
    ['getTrip', () => api.getTrip(3), '/trips/3', 'GET', undefined],
    ['createTrip', () => api.createTrip({ name: 'Praca', origin: 'Gdańsk', destination: 'Sopot' }), '/trips', 'POST',
      { name: 'Praca', origin: 'Gdańsk', destination: 'Sopot' }],
    ['updateTrip', () => api.updateTrip(3, { notes: null }), '/trips/3', 'PUT', { notes: null }],
    ['getComparison', () => api.getComparison(3), '/trips/3/comparison', 'GET', undefined],
    ['parseTrip', () => api.parseTrip('z Oliwy do Wrzeszcza'), '/parse', 'POST', { text: 'z Oliwy do Wrzeszcza' }],
  ])('%s', async (_name, call, path, method, body) => {
    const fetchFn = mockFetch(json(200, {}))
    await call()
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_URL}${path}`)
    expect(init.method ?? 'GET').toBe(method)
    expect(init.body === undefined ? undefined : JSON.parse(init.body as string)).toEqual(body)
  })

  it('deleteTrip', async () => {
    const fetchFn = mockFetch(new Response(null, { status: 204 }))
    await expect(api.deleteTrip(3)).resolves.toBeUndefined()
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit]
    expect([url, init.method]).toEqual([`${API_URL}/trips/3`, 'DELETE'])
  })
})

describe('errorText', () => {
  it('uses the ApiError message', () => {
    expect(errorText(new ApiError(503, 'niedostępne'))).toBe('niedostępne')
  })

  it('hides details of unexpected errors', () => {
    expect(errorText(new TypeError('x is undefined'))).toBe('Wystąpił nieoczekiwany błąd.')
  })
})

describe('errorMessage — POST /api/parse', () => {
  it('translates NoRouteFoundError', () => {
    expect(errorMessage(422, { detail: 'No route found in the text' })).toBe(
      'Nie rozpoznano trasy. Napisz np. „z Oliwy do Wrzeszcza” albo „Do pracy: z Sopotu do Gdyni”.',
    )
  })

  it('labels the text field in validation errors', () => {
    const detail = [{ loc: ['body', 'text'], type: 'string_too_long', msg: 'too long', ctx: { max_length: 500 } }]
    expect(errorMessage(422, { detail })).toBe('Opis: za długie (maks. 500 znaków)')
  })

  it('keeps the text limit in sync with the backend default', () => {
    expect(PARSE_TEXT_MAX_LENGTH).toBe(500)
  })
})
