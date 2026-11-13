import type { Trip } from './api'

interface Props {
  trips: Trip[]
  loading: boolean
  /** Error while loading the list; shown instead of the list, with a retry button. */
  error: string | null
  /** Error of the last action on the list (e.g. delete); shown above the list. */
  actionError: string | null
  onRetry: () => void
  onEdit: (trip: Trip) => void
  onDelete: (trip: Trip) => void
}

export default function TripList({ trips, loading, error, actionError, onRetry, onEdit, onDelete }: Props) {
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
            <li key={trip.id} className="rounded border border-slate-200 bg-white p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{trip.name}</p>
                  <p className="text-sm text-slate-600">
                    {trip.origin} → {trip.destination}
                  </p>
                  {trip.notes && <p className="mt-1 text-sm whitespace-pre-line text-slate-500">{trip.notes}</p>}
                </div>
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
