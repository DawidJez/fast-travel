import { useState, type FormEvent } from 'react'
import { api, errorText, type Trip, type TripCreate } from './api'

// Same limits as backend/app/config.py (TRIP_*_MAX_LENGTH); the backend still validates.
const MAX_NAME = 100
const MAX_PLACE = 200
const MAX_NOTES = 1000

interface Props {
  /** Trip being edited, or null to add a new one. */
  trip: Trip | null
  onSaved: (trip: Trip) => void
  onCancel: () => void
}

interface Values {
  name: string
  origin: string
  destination: string
  notes: string
}

const EMPTY: Values = { name: '', origin: '', destination: '', notes: '' }

function initialValues(trip: Trip | null): Values {
  return trip
    ? { name: trip.name, origin: trip.origin, destination: trip.destination, notes: trip.notes ?? '' }
    : EMPTY
}

/** Form values -> request body (empty notes are sent as null). */
function toPayload(values: Values): TripCreate {
  return {
    name: values.name,
    origin: values.origin,
    destination: values.destination,
    notes: values.notes.trim() === '' ? null : values.notes,
  }
}

const inputClass = 'mt-1 w-full rounded border border-slate-300 px-2 py-1 disabled:bg-slate-100'

/** Add / edit form. Remount it (key) when switching trips so it starts from that trip's values. */
export default function TripForm({ trip, onSaved, onCancel }: Props) {
  const [values, setValues] = useState<Values>(() => initialValues(trip))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = (field: keyof Values) => (event: { target: { value: string } }) =>
    setValues((current) => ({ ...current, [field]: event.target.value }))

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = toPayload(values)
      const saved = trip ? await api.updateTrip(trip.id, payload) : await api.createTrip(payload)
      if (!trip) setValues(EMPTY)
      onSaved(saved)
    } catch (caught) {
      setError(errorText(caught))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <h2 className="text-lg font-semibold">{trip ? 'Edytuj trasę' : 'Nowa trasa'}</h2>

      <label className="block">
        <span className="text-sm font-medium">Nazwa</span>
        <input className={inputClass} value={values.name} onChange={set('name')} required maxLength={MAX_NAME} disabled={saving} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Skąd</span>
        <input className={inputClass} value={values.origin} onChange={set('origin')} required maxLength={MAX_PLACE} disabled={saving} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Dokąd</span>
        <input className={inputClass} value={values.destination} onChange={set('destination')} required maxLength={MAX_PLACE} disabled={saving} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Notatka</span>
        <textarea className={inputClass} value={values.notes} onChange={set('notes')} maxLength={MAX_NOTES} rows={2} disabled={saving} />
      </label>

      {error && (
        <p role="alert" className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-800">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button type="submit" disabled={saving} className="rounded bg-blue-700 px-3 py-1 text-white disabled:opacity-60">
          {saving ? 'Zapisywanie…' : trip ? 'Zapisz zmiany' : 'Dodaj trasę'}
        </button>
        {trip && (
          <button type="button" onClick={onCancel} disabled={saving} className="rounded border border-slate-300 px-3 py-1">
            Anuluj
          </button>
        )}
      </div>
    </form>
  )
}
