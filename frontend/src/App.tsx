import { useCallback, useEffect, useRef, useState } from 'react'
import { api, errorText, type Trip } from './api/client'
import ComparisonView from './components/ComparisonView'
import TripForm from './components/TripForm'
import TripList from './components/TripList'
import { card } from './ui'

/** On narrow screens (one column) bring a section into view; on wide screens everything is visible. */
function revealOnMobile(element: HTMLElement | null) {
  if (window.matchMedia?.('(max-width: 1023px)').matches) element?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

export default function App() {
  const [trips, setTrips] = useState<Trip[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Trip | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = trips.find((t) => t.id === selectedId) ?? null
  const formRef = useRef<HTMLDivElement>(null)
  const comparisonRef = useRef<HTMLElement>(null)

  // `loading` starts as true; the retry button sets it again before calling this.
  // State is set only in the promise callbacks, never synchronously.
  const fetchTrips = useCallback(
    () =>
      api
        .listTrips()
        .then(setTrips, (caught: unknown) => setListError(errorText(caught)))
        .finally(() => setLoading(false)),
    [],
  )

  useEffect(() => {
    void fetchTrips()
  }, [fetchTrips])

  function retry() {
    setLoading(true)
    setListError(null)
    void fetchTrips()
  }

  function handleSaved(saved: Trip) {
    setActionError(null)
    setTrips((current) =>
      current.some((t) => t.id === saved.id)
        ? current.map((t) => (t.id === saved.id ? saved : t))
        : [saved, ...current], // list is newest first, like the API
    )
    setEditing(null)
  }

  async function handleDelete(trip: Trip) {
    if (!window.confirm(`Usunąć trasę „${trip.name}”?`)) return
    setActionError(null)
    try {
      await api.deleteTrip(trip.id)
      setTrips((current) => current.filter((t) => t.id !== trip.id))
      if (editing?.id === trip.id) setEditing(null)
      if (selectedId === trip.id) setSelectedId(null)
    } catch (caught) {
      setActionError(errorText(caught))
    }
  }

  function handleSelect(trip: Trip) {
    setSelectedId(trip.id)
    revealOnMobile(comparisonRef.current)
  }

  function handleEdit(trip: Trip) {
    setEditing(trip)
    revealOnMobile(formRef.current)
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4">
          <span className="text-3xl" aria-hidden="true">🧭</span>
          <div>
            <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Fast Travel</h1>
            <p className="text-sm text-slate-500">Porównaj dojazd: czas, koszt i CO₂ dla każdego środka transportu.</p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-6xl flex-1 content-start gap-6 px-4 py-6 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)] lg:items-start">
        <div className="space-y-6">
          <div ref={formRef} className="scroll-mt-4">
            <TripForm
              key={editing?.id ?? 'new'}
              trip={editing}
              onSaved={handleSaved}
              onCancel={() => setEditing(null)}
            />
          </div>
          <section aria-labelledby="trips-heading">
            <h2 id="trips-heading" className="mb-3 text-lg font-semibold">
              Zapisane trasy{!loading && !listError && trips.length > 0 && (
                <span className="ml-2 text-sm font-normal text-slate-500">({trips.length})</span>
              )}
            </h2>
            <TripList
              trips={trips}
              loading={loading}
              error={listError}
              actionError={actionError}
              selectedId={selectedId}
              onRetry={retry}
              onSelect={handleSelect}
              onEdit={handleEdit}
              onDelete={(trip) => void handleDelete(trip)}
            />
          </section>
        </div>

        <section ref={comparisonRef} aria-label="Porównanie" className={`${card} scroll-mt-4 p-5 lg:sticky lg:top-6`}>
          {selected ? (
            // A new key reloads the comparison when another trip is chosen or its places are edited.
            <ComparisonView key={`${selected.id}|${selected.origin}|${selected.destination}`} tripId={selected.id} />
          ) : (
            <div className="py-10 text-center text-slate-500">
              <p className="text-4xl" aria-hidden="true">🚶 🚲 🚗 🚋</p>
              <p className="mt-3">Wybierz trasę z listy, aby zobaczyć porównanie.</p>
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <p className="mx-auto max-w-6xl px-4 py-3 text-xs text-slate-500">
          Geokodowanie: ©{' '}
          <a href="https://www.openstreetmap.org/copyright" className="underline hover:text-slate-700" target="_blank" rel="noreferrer">
            OpenStreetMap contributors
          </a>
          {' · '}
          <a href="https://open-meteo.com/" className="underline hover:text-slate-700" target="_blank" rel="noreferrer">
            Open-Meteo
          </a>
          {' '}(geokodowanie i pogoda) · Wyniki są szacunkowe.
        </p>
      </footer>
    </div>
  )
}
