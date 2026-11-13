import { useCallback, useEffect, useState } from 'react'
import { api, errorText, type Trip } from './api'
import ComparisonView from './ComparisonView'
import TripForm from './TripForm'
import TripList from './TripList'

export default function App() {
  const [trips, setTrips] = useState<Trip[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Trip | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = trips.find((t) => t.id === selectedId) ?? null

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

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <main className="mx-auto max-w-5xl space-y-4 p-4">
        <h1 className="text-2xl font-semibold">Fast Travel</h1>
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <TripForm
            key={editing?.id ?? 'new'}
            trip={editing}
            onSaved={handleSaved}
            onCancel={() => setEditing(null)}
          />
          <section>
            <h2 className="mb-2 text-lg font-semibold">Zapisane trasy</h2>
            <TripList
              trips={trips}
              loading={loading}
              error={listError}
              actionError={actionError}
              selectedId={selectedId}
              onRetry={retry}
              onSelect={(trip) => setSelectedId(trip.id)}
              onEdit={setEditing}
              onDelete={(trip) => void handleDelete(trip)}
            />
          </section>
        </div>
        <section className="rounded border border-slate-200 bg-white p-4">
          {selected ? (
            // A new key reloads the comparison when another trip is chosen or its places are edited.
            <ComparisonView key={`${selected.id}|${selected.origin}|${selected.destination}`} tripId={selected.id} />
          ) : (
            <p className="text-slate-500">Wybierz trasę z listy, aby zobaczyć porównanie.</p>
          )}
        </section>
      </main>
      <footer className="mx-auto max-w-5xl p-4 text-xs text-slate-500">
        Geokodowanie: © OpenStreetMap contributors
      </footer>
    </div>
  )
}
