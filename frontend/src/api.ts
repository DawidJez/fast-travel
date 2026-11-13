/**
 * Backend API: types mirroring backend/app/schemas.py and a thin fetch wrapper.
 * Errors from FastAPI are turned into an ApiError with a readable (Polish) message.
 */

// --- Types (keep in sync with backend/app/schemas.py) ---

export type Mode = 'walk' | 'bike' | 'car' | 'public_transport'

/** TripRead */
export interface Trip {
  id: number
  name: string
  origin: string
  destination: string
  notes: string | null
  origin_lat: number
  origin_lon: number
  destination_lat: number
  destination_lon: number
  /** ISO 8601, UTC */
  created_at: string
}

/** TripCreate: coordinates are set by the server (geocoding). */
export interface TripCreate {
  name: string
  origin: string
  destination: string
  notes?: string | null
}

/** TripUpdate: partial; only sent fields change. name/origin/destination cannot be null. */
export interface TripUpdate {
  name?: string
  origin?: string
  destination?: string
  notes?: string | null
}

/** ModeComparisonRead */
export interface ModeComparison {
  mode: Mode
  distance_km: number
  time_minutes: number
  cost_pln: number
  co2_grams: number
  /** True when the figures are a rough estimate (public transport). */
  estimate: boolean
  note: string | null
}

/** WeatherRead */
export interface Weather {
  temperature_c: number
  precipitation_mm: number
  wind_speed_kmh: number
}

/** RecommendationRead */
export interface Recommendation {
  mode: Mode
  reason: string
}

/** TripComparisonRead */
export interface Comparison {
  trip_id: number
  origin: string
  destination: string
  straight_line_km: number
  car_peak: boolean
  /** null when the weather service is unavailable */
  weather: Weather | null
  modes: ModeComparison[]
  recommendation: Recommendation
}

// --- Errors ---

export class ApiError extends Error {
  /** HTTP status; 0 when the server could not be reached. */
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** One item of FastAPI's 422 validation error list. */
interface ValidationIssue {
  loc?: (string | number)[]
  msg?: string
  type?: string
  ctx?: { max_length?: number }
}

const FIELD_LABELS: Record<string, string> = {
  name: 'Nazwa',
  origin: 'Skąd',
  destination: 'Dokąd',
  notes: 'Notatki',
}

function describeIssue(issue: ValidationIssue): string {
  const field = issue.loc?.[issue.loc.length - 1]
  const label = typeof field === 'string' ? FIELD_LABELS[field] ?? field : undefined
  let problem: string
  switch (issue.type) {
    case 'missing':
    case 'string_too_short':
      problem = 'pole jest wymagane'
      break
    case 'string_too_long':
      problem = `za długie (maks. ${issue.ctx?.max_length ?? '?'} znaków)`
      break
    default:
      problem = issue.msg ?? 'nieprawidłowa wartość'
  }
  return label ? `${label}: ${problem}` : problem
}

/** Turn an error response (status + parsed JSON body, if any) into a readable message. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail

  if (typeof detail === 'string') {
    // PlaceNotFoundError: "Place not found: 'Xyz'" (Python repr, ' or " quotes)
    const place = /^Place not found: (['"])(.*)\1$/.exec(detail)
    if (place) return `Nie znaleziono miejsca „${place[2]}”. Sprawdź pisownię lub podaj dokładniejszą nazwę.`
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((issue: ValidationIssue) => describeIssue(issue)).join('; ')
  }
  if (status === 404) return 'Nie znaleziono podróży (mogła zostać usunięta).'
  if (status === 503) return 'Wyszukiwanie miejsc jest chwilowo niedostępne. Spróbuj ponownie za chwilę.'
  if (status === 422) return 'Nieprawidłowe dane.'
  return `Błąd serwera (HTTP ${status}).`
}

// --- Fetch wrapper ---

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api').replace(/\/+$/, '')

/** fetch + JSON. Throws ApiError with a readable message on network or HTTP errors. */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, `Brak połączenia z serwerem (${API_URL}). Czy backend jest uruchomiony?`)
  }

  if (response.status === 204) return undefined as T

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // not JSON (e.g. an HTML error page): handled below
  }

  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body))
  if (body === null) throw new ApiError(response.status, 'Nieprawidłowa odpowiedź serwera.')
  return body as T
}

// --- Endpoints ---

export const api = {
  listTrips: () => request<Trip[]>('/trips'),
  getTrip: (id: number) => request<Trip>(`/trips/${id}`),
  createTrip: (data: TripCreate) => request<Trip>('/trips', { method: 'POST', body: JSON.stringify(data) }),
  updateTrip: (id: number, data: TripUpdate) =>
    request<Trip>(`/trips/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTrip: (id: number) => request<void>(`/trips/${id}`, { method: 'DELETE' }),
  getComparison: (id: number) => request<Comparison>(`/trips/${id}/comparison`),
}
