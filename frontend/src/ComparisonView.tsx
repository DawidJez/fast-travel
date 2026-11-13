import { useEffect, useState } from 'react'
import { api, errorText, type Comparison, type ModeComparison } from './api'
import {
  MODE_ICONS, MODE_LABELS, formatClock, formatGrams, formatKm, formatMinutes, formatPln, formatWeather,
} from './format'
import Spinner, { Loading } from './Spinner'
import { alert, button } from './ui'

interface Props {
  tripId: number
}

interface Loaded {
  comparison: Comparison
  /** When this comparison was fetched: weather and rush hour are "now" at that moment. */
  at: Date
}

/** Comparison of one trip. Remount it (key) to load another trip or reload after an edit. */
export default function ComparisonView({ tripId }: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true // ignore a late answer after unmount
    api
      .getComparison(tripId)
      .then(
        (comparison) => {
          if (!active) return
          setLoaded({ comparison, at: new Date() })
          setError(null)
        },
        (caught: unknown) => active && setError(errorText(caught)),
      )
      .finally(() => active && setRefreshing(false))
    return () => {
      active = false
    }
  }, [tripId, attempt])

  /** Fetch again (new weather, rush hour); the old figures stay visible meanwhile. */
  function refresh() {
    setRefreshing(true)
    setError(null)
    setAttempt((n) => n + 1)
  }

  if (!loaded && !error) return <Loading text="Liczenie porównania…" />

  const data = loaded?.comparison
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold break-words text-slate-900">
            {data ? `${data.origin} → ${data.destination}` : 'Porównanie'}
          </h2>
          {data && loaded && (
            <p className="text-sm text-slate-500">
              W linii prostej: {formatKm(data.straight_line_km)} · stan na {formatClock(loaded.at)}
            </p>
          )}
        </div>
        {data && (
          <button type="button" onClick={refresh} disabled={refreshing} className={button.secondary}>
            {refreshing ? <Spinner /> : <span aria-hidden="true">↻</span>}
            {refreshing ? 'Przeliczanie…' : 'Odśwież'}
          </button>
        )}
      </div>

      {error && (
        <div role="alert" className={alert}>
          <p>Nie udało się pobrać porównania: {error}</p>
          <button type="button" onClick={refresh} className={`${button.secondary} mt-3`}>
            Spróbuj ponownie
          </button>
        </div>
      )}

      {data && (
        <div className={`space-y-5 transition-opacity ${refreshing ? 'opacity-60' : ''}`}>
          <div className="flex gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <span className="text-3xl leading-none" aria-hidden="true">
              {MODE_ICONS[data.recommendation.mode]}
            </span>
            <div className="min-w-0">
              <p className="text-xs font-semibold tracking-wide text-emerald-700 uppercase">Rekomendacja</p>
              <p className="text-lg font-semibold text-emerald-950">Polecamy: {MODE_LABELS[data.recommendation.mode]}</p>
              <p className="mt-1 text-sm text-emerald-900">{data.recommendation.reason}</p>
            </div>
          </div>

          <p className="flex items-start gap-2 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">
            <span aria-hidden="true">{data.weather ? '🌤️' : '❔'}</span>
            <span>
              {data.weather
                ? `Pogoda teraz w punkcie startu: ${formatWeather(data.weather)}.`
                : 'Brak danych pogodowych — pogoda nie została uwzględniona w rekomendacji.'}
            </span>
          </p>

          <ul className="grid gap-3 sm:grid-cols-2">
            {data.modes.map((mode) => (
              <ModeCard
                key={mode.mode}
                mode={mode}
                recommended={mode.mode === data.recommendation.mode}
                carPeak={data.car_peak}
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ModeCard({ mode, recommended, carPeak }: { mode: ModeComparison; recommended: boolean; carPeak: boolean }) {
  return (
    <li
      aria-label={MODE_LABELS[mode.mode]}
      className={`flex flex-col rounded-xl border bg-white p-4 shadow-sm ${
        recommended ? 'border-emerald-500 ring-2 ring-emerald-100' : 'border-slate-200'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xl leading-none" aria-hidden="true">
          {MODE_ICONS[mode.mode]}
        </span>
        <h3 className="font-semibold text-slate-900">{MODE_LABELS[mode.mode]}</h3>
        {recommended && (
          <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white">polecane</span>
        )}
        {mode.estimate && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">szacunek</span>
        )}
      </div>

      <p className="mt-3 text-2xl font-semibold text-slate-900 tabular-nums">{formatMinutes(mode.time_minutes)}</p>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-xs text-slate-500">Koszt</dt>
          <dd className="font-medium tabular-nums">{formatPln(mode.cost_pln)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">CO₂</dt>
          <dd className="font-medium tabular-nums">{formatGrams(mode.co2_grams)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Dystans</dt>
          <dd className="font-medium tabular-nums">{formatKm(mode.distance_km)}</dd>
        </div>
      </dl>

      {mode.mode === 'car' && carPeak && (
        <p className="mt-3 rounded-md bg-orange-50 px-2 py-1 text-xs text-orange-800">
          Godziny szczytu: doliczono czas i emisję w korku.
        </p>
      )}
      {mode.note && <p className="mt-3 text-xs text-slate-500">{mode.note}</p>}
    </li>
  )
}
