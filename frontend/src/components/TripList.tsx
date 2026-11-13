import type { Trip } from '../api/client'
import { Loading } from './Spinner'
import { alert, button } from '../ui'

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
  if (loading) return <Loading text="Ładowanie tras…" />

  if (error) {
    return (
      <div role="alert" className={alert}>
        <p>Nie udało się pobrać tras: {error}</p>
        <button type="button" onClick={onRetry} className={`${button.secondary} mt-3`}>
          Spróbuj ponownie
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {actionError && (
        <p role="alert" className={alert}>
          {actionError}
        </p>
      )}
      {trips.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          Brak zapisanych tras. Dodaj pierwszą w formularzu.
        </p>
      ) : (
        <ul className="space-y-2">
          {trips.map((trip) => {
            const selected = trip.id === selectedId
            return (
              <li
                key={trip.id}
                className={`rounded-xl border bg-white shadow-sm transition ${
                  selected ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-start gap-2 p-3">
                  <button
                    type="button"
                    onClick={() => onSelect(trip)}
                    aria-pressed={selected}
                    title="Pokaż porównanie"
                    className="min-w-0 flex-1 rounded-md text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  >
                    <span className="block truncate font-medium text-slate-900">{trip.name}</span>
                    <span className="block text-sm break-words text-slate-600">
                      {trip.origin} → {trip.destination}
                    </span>
                    {trip.notes && (
                      <span className="mt-1 block text-sm whitespace-pre-line text-slate-500">{trip.notes}</span>
                    )}
                    <span className={`mt-1 block text-xs font-medium ${selected ? 'text-blue-700' : 'text-slate-400'}`}>
                      {selected ? 'Wybrana do porównania' : 'Kliknij, aby porównać'}
                    </span>
                  </button>
                  <div className="flex shrink-0 gap-1">
                    <button type="button" onClick={() => onEdit(trip)} className={`${button.small} text-blue-700 hover:bg-blue-50`}>
                      Edytuj
                    </button>
                    <button type="button" onClick={() => onDelete(trip)} className={`${button.small} text-red-700 hover:bg-red-50`}>
                      Usuń
                    </button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
