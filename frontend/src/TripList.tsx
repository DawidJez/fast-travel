import type { Trip } from './api'

interface Props {
  trips: Trip[]
  loading: boolean
  /** Error while loading the list; shown instead of the list, with a retry button. */
  error: string | null
  /** Error of the last action on the list (e.g. delete); shown above the list. */
  actionError: string | null
  /** Trip whose comparison is shown; highlighted in the list. */
  selectedId: number | null
  onRetry: () => void
  onSelect: (trip: Trip) => void
  onEdit: (trip: Trip) => void
  onDelete: (trip: Trip) => void
}

export default function TripList({
  trips, loading, error, actionError, selectedId, onRetry, onSelect, onEdit, onDelete,
}: Props) {
  if (loading) return <p className="text-slate-500">Ładowanie tras…</p>

  if (error) {
    return (
      <div role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
        <p>Nie udało się pobrać tras: {error}</p>
        <button type="button" onClick={onRetry} className="mt-2 underline">
          Spróbuj ponownie
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {actionError && (
        <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
          {actionError}
        </p>
      )}
      {trips.length === 0 ? (
        <p className="text-slate-500">Brak zapisanych tras. Dodaj pierwszą w formularzu.</p>
      ) : (
        <ul className="space-y-2">
          {trips.map((trip) => (
            <li
              key={trip.id}
              className={`rounded border bg-white p-3 ${trip.id === selectedId ? 'border-blue-500 ring-1 ring-blue-500' : 'border-slate-200'}`}
            >
              <div className="flex items-start justify-between gap-3">
                <button
                  type="button"
                  onClick={() => onSelect(trip)}
                  aria-pressed={trip.id === selectedId}
                  title="Pokaż porównanie"
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block font-medium">{trip.name}</span>
                  <span className="block text-sm text-slate-600">
                    {trip.origin} → {trip.destination}
                  </span>
                  {trip.notes && <span className="mt-1 block text-sm whitespace-pre-line text-slate-500">{trip.notes}</span>}
                </button>
                <div className="flex shrink-0 gap-2 text-sm">
                  <button type="button" onClick={() => onEdit(trip)} className="text-blue-700 hover:underline">
                    Edytuj
                  </button>
                  <button type="button" onClick={() => onDelete(trip)} className="text-red-700 hover:underline">
                    Usuń
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
