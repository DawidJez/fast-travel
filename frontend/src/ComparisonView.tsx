import { useEffect, useState } from 'react'
import { api, errorText, type Comparison, type ModeComparison } from './api'
import { MODE_LABELS, formatGrams, formatKm, formatMinutes, formatPln, formatWeather } from './format'

interface Props {
  tripId: number
}

/** Comparison of one trip. Remount it (key) to load another trip or reload after an edit. */
export default function ComparisonView({ tripId }: Props) {
  const [data, setData] = useState<Comparison | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true // ignore a late answer after unmount
    api.getComparison(tripId).then(
      (comparison) => active && setData(comparison),
      (caught: unknown) => active && setError(errorText(caught)),
    )
    return () => {
      active = false
    }
  }, [tripId, attempt])

  function retry() {
    setError(null)
    setAttempt((n) => n + 1)
  }

  if (error) {
    return (
      <div role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
        <p>Nie udało się pobrać porównania: {error}</p>
        <button type="button" onClick={retry} className="mt-2 underline">
          Spróbuj ponownie
        </button>
      </div>
    )
  }
  if (!data) return <p className="text-slate-500">Liczenie porównania…</p>

  const recommended = data.recommendation.mode
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">
          {data.origin} → {data.destination}
        </h2>
        <p className="text-sm text-slate-600">W linii prostej: {formatKm(data.straight_line_km)}</p>
      </div>

      <div className="rounded border border-green-300 bg-green-50 p-3">
        <p className="font-medium text-green-900">Polecamy: {MODE_LABELS[recommended]}</p>
        <p className="mt-1 text-sm text-green-900">{data.recommendation.reason}</p>
      </div>

      <p className="text-sm text-slate-700">
        {data.weather
          ? `Pogoda teraz w punkcie startu: ${formatWeather(data.weather)}.`
          : 'Brak danych pogodowych — pogoda nie została uwzględniona w rekomendacji.'}
      </p>

      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {data.modes.map((mode) => (
          <ModeCard key={mode.mode} mode={mode} recommended={mode.mode === recommended} carPeak={data.car_peak} />
        ))}
      </ul>
    </div>
  )
}

function ModeCard({ mode, recommended, carPeak }: { mode: ModeComparison; recommended: boolean; carPeak: boolean }) {
  return (
    <li
      aria-label={MODE_LABELS[mode.mode]}
      className={`rounded border bg-white p-3 ${recommended ? 'border-green-500 ring-2 ring-green-500' : 'border-slate-200'}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{MODE_LABELS[mode.mode]}</h3>
        {recommended && <span className="rounded bg-green-600 px-1.5 py-0.5 text-xs text-white">polecane</span>}
        {mode.estimate && <span className="rounded bg-amber-200 px-1.5 py-0.5 text-xs text-amber-900">szacunek</span>}
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
        <dt className="text-slate-500">Czas</dt>
        <dd>{formatMinutes(mode.time_minutes)}</dd>
        <dt className="text-slate-500">Koszt</dt>
        <dd>{formatPln(mode.cost_pln)}</dd>
        <dt className="text-slate-500">CO₂</dt>
        <dd>{formatGrams(mode.co2_grams)}</dd>
        <dt className="text-slate-500">Dystans</dt>
        <dd>{formatKm(mode.distance_km)}</dd>
      </dl>
      {mode.mode === 'car' && carPeak && (
        <p className="mt-2 text-xs text-slate-600">Godziny szczytu: doliczono czas i emisję w korku.</p>
      )}
      {mode.note && <p className="mt-2 text-xs text-slate-600">{mode.note}</p>}
    </li>
  )
}
