import { useState, type FormEvent, type ReactNode } from 'react'
import { api, errorText, type Trip, type TripCreate } from '../api/client'
import Spinner from './Spinner'
import { alert, button, card } from '../ui'

// Same limits as backend/app/config.py (TRIP_*_MAX_LENGTH); the backend still validates.
const MAX_NAME = 100
const MAX_PLACE = 200
const MAX_NOTES = 1000

interface Props {
  /** Trip being edited, or null to add a new one. */
  trip: Trip | null
  /** `created` is true for a new trip (POST), false for an edit (PUT). */
  onSaved: (trip: Trip, created: boolean) => void
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

const inputClass =
  'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-xs placeholder:text-slate-400 ' +
  'focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none disabled:bg-slate-100 disabled:text-slate-500'

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label className="block">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        {children}
      </label>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

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
      onSaved(saved, !trip)
    } catch (caught) {
      setError(errorText(caught))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className={`${card} space-y-4 p-5`}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{trip ? 'Edytuj trasę' : 'Nowa trasa'}</h2>
        {trip && <p className="text-sm text-slate-500">Zmieniasz „{trip.name}”.</p>}
      </div>

      <Field label="Nazwa">
        <input className={inputClass} value={values.name} onChange={set('name')} required maxLength={MAX_NAME}
          disabled={saving} placeholder="np. Do pracy" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
        <Field label="Skąd">
          <input className={inputClass} value={values.origin} onChange={set('origin')} required maxLength={MAX_PLACE}
            disabled={saving} placeholder="np. Gdańsk Wrzeszcz" />
        </Field>
        <Field label="Dokąd">
          <input className={inputClass} value={values.destination} onChange={set('destination')} required
            maxLength={MAX_PLACE} disabled={saving} placeholder="np. Politechnika Gdańska" />
        </Field>
      </div>
      <p className="-mt-2 text-xs text-slate-500">Miejscowość, dzielnica, adres lub nazwa miejsca.</p>
      <Field label="Notatka" hint="Opcjonalnie.">
        <textarea className={inputClass} value={values.notes} onChange={set('notes')} maxLength={MAX_NOTES} rows={2}
          disabled={saving} />
      </Field>

      {error && (
        <p role="alert" className={alert}>
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={saving} className={button.primary}>
          {saving && <Spinner />}
          {saving ? 'Zapisywanie…' : trip ? 'Zapisz zmiany' : 'Dodaj trasę'}
        </button>
        {trip && (
          <button type="button" onClick={onCancel} disabled={saving} className={button.secondary}>
            Anuluj
          </button>
        )}
      </div>
    </form>
  )
}
