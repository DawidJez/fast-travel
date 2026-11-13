/** Display helpers (Polish number format) for comparison figures. */

import type { Mode, Weather } from './api/client'

export const MODE_LABELS: Record<Mode, string> = {
  walk: 'Pieszo',
  bike: 'Rower',
  car: 'Samochód',
  public_transport: 'Komunikacja miejska',
}

/** Decorative icons next to the labels (hidden from screen readers). */
export const MODE_ICONS: Record<Mode, string> = {
  walk: '🚶',
  bike: '🚲',
  car: '🚗',
  public_transport: '🚋',
}

const number = (value: number, decimals: number) =>
  value.toLocaleString('pl-PL', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })

/** Whole minutes, like the backend's "ok. N min"; an hour or more as "1 h 05 min". */
export function formatMinutes(minutes: number): string {
  const total = Math.round(minutes)
  if (total < 60) return `ok. ${total} min`
  const rest = total % 60
  return `ok. ${Math.floor(total / 60)} h ${String(rest).padStart(2, '0')} min`
}

export const formatPln = (pln: number) => `${number(pln, 2)} zł`

export const formatKm = (km: number) => `${number(km, 1)} km`

export const formatGrams = (grams: number) => `${number(grams, 0)} g`

export function formatWeather(weather: Weather): string {
  return [
    `${number(weather.temperature_c, 1)} °C`,
    `opady ${number(weather.precipitation_mm, 1)} mm`,
    `wiatr ${number(weather.wind_speed_kmh, 0)} km/h`,
  ].join(', ')
}

/** Local clock time "HH:MM", e.g. when a comparison was calculated. */
export const formatClock = (date: Date) => date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })
