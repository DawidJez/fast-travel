import { describe, expect, it } from 'vitest'
import { MODE_ICONS, MODE_LABELS, formatClock, formatGrams, formatKm, formatMinutes, formatPln, formatWeather } from './format'

// toLocaleString('pl-PL') may use a (narrow) no-break space as thousands separator.
const normalize = (text: string) => text.replace(/[  ]/g, ' ')

describe('format', () => {
  it.each([
    [0, 'ok. 0 min'],
    [16.9, 'ok. 17 min'],
    [59.4, 'ok. 59 min'],
    [59.6, 'ok. 1 h 00 min'],
    [65, 'ok. 1 h 05 min'],
    [150.2, 'ok. 2 h 30 min'],
  ])('formatMinutes(%s)', (minutes, text) => {
    expect(formatMinutes(minutes)).toBe(text)
  })

  it('formats money, distance and CO2 the Polish way', () => {
    expect(formatPln(6)).toBe('6,00 zł')
    expect(formatPln(7.5)).toBe('7,50 zł')
    expect(formatKm(12.3)).toBe('12,3 km')
    expect(formatKm(0)).toBe('0,0 km')
    expect(formatGrams(919)).toBe('919 g')
    expect(normalize(formatGrams(12345))).toBe('12 345 g')
  })

  it('summarises the weather', () => {
    expect(formatWeather({ temperature_c: -2.5, precipitation_mm: 1.2, wind_speed_kmh: 39.4 })).toBe(
      '-2,5 °C, opady 1,2 mm, wiatr 39 km/h',
    )
  })

  it('has a label for every mode', () => {
    expect(Object.keys(MODE_LABELS).sort()).toEqual(['bike', 'car', 'public_transport', 'walk'])
  })

  it('has an icon for every mode', () => {
    expect(Object.keys(MODE_ICONS).sort()).toEqual(Object.keys(MODE_LABELS).sort())
  })

  it('formats the clock as HH:MM', () => {
    expect(formatClock(new Date(2026, 10, 13, 8, 5))).toBe('08:05')
  })
})
