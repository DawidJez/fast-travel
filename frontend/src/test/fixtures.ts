import type { Comparison, Trip } from '../api'

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

export function makeComparison(overrides: Partial<Comparison> = {}): Comparison {
  const note = 'Szacunek na podstawie średniej prędkości autobusu/tramwaju, bez rozkładów jazdy i kolei (np. SKM).'
  return {
    trip_id: 1,
    origin: 'Gdańsk Wrzeszcz',
    destination: 'Gdańsk Oliwa',
    straight_line_km: 4.2,
    car_peak: false,
    weather: { temperature_c: 3.8, precipitation_mm: 0, wind_speed_kmh: 10 },
    modes: [
      { mode: 'walk', distance_km: 5, time_minutes: 60.4, cost_pln: 0, co2_grams: 0, estimate: false, note: null },
      { mode: 'bike', distance_km: 5, time_minutes: 20.2, cost_pln: 0, co2_grams: 0, estimate: false, note: null },
      { mode: 'car', distance_km: 5.5, time_minutes: 16.9, cost_pln: 6.33, co2_grams: 919, estimate: false, note: null },
      { mode: 'public_transport', distance_km: 5.5, time_minutes: 33, cost_pln: 6, co2_grams: 572, estimate: true, note },
    ],
    recommendation: {
      mode: 'bike',
      reason: 'Rower (ok. 20 min) zamiast samochodu (ok. 17 min): o 3 min dłużej, ale oszczędzasz 6,33 zł i 919 g CO₂.',
    },
    ...overrides,
  }
}
