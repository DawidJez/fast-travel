import type { Trip } from '../api'

export function makeTrip(overrides: Partial<Trip> = {}): Trip {
  return {
    id: 1,
    name: 'Praca',
    origin: 'Gdańsk Wrzeszcz',
    destination: 'Gdańsk Oliwa',
    notes: null,
    origin_lat: 54.38,
    origin_lon: 18.6,
    destination_lat: 54.41,
    destination_lon: 18.56,
    created_at: '2026-11-13T10:00:00Z',
    ...overrides,
  }
}
