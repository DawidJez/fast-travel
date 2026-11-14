import { useState, type FormEvent } from 'react'
import { api, errorText, PARSE_TEXT_MAX_LENGTH, type ParsedTrip } from '../api/client'
import Spinner from './Spinner'
import { alert, button, card } from '../ui'

interface Props {
  /** Called right when the user asks to fill the form (before the answer arrives). */
  onStart: () => void
  /** Called with the recognised fields; they prefill the new-trip form. */
  onParsed: (parsed: ParsedTrip) => void
}

const MISSING_LABELS = { origin: 'Skąd', destination: 'Dokąd' } as const

/** "Describe the trip in your own words" -> POST /api/parse -> prefill the form (the user reviews it before saving). */
export default function TripParser({ onStart, onParsed }: Props) {
  const [text, setText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ParsedTrip | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setParsing(true)
    setError(null)
    setResult(null)
    onStart()
    try {
      const parsed = await api.parseTrip(text)
      setResult(parsed)
      onParsed(parsed)
    } catch (caught) {
      setError(errorText(caught))
    } finally {
      setParsing(false)
    }
  }

  const missing = result
    ? (Object.keys(MISSING_LABELS) as (keyof typeof MISSING_LABELS)[]).filter((field) => result[field] === null)
    : []

  return (
    <form onSubmit={handleSubmit} className={`${card} space-y-3 p-5`}>
      <label className="block">
        <span className="text-sm font-medium text-slate-700">Opisz trasę własnymi słowami</span>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          required
          maxLength={PARSE_TEXT_MAX_LENGTH}
          rows={2}
          disabled={parsing}
          placeholder="np. Do pracy: rano z Oliwy na Politechnikę Gdańską"
          className={
            'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-xs placeholder:text-slate-400 ' +
            'focus:border-violet-500 focus:ring-2 focus:ring-violet-200 focus:outline-none disabled:bg-slate-100 disabled:text-slate-500'
          }
        />
      </label>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="submit" disabled={parsing || text.trim() === ''} className={button.secondary}>
          {parsing ? <Spinner /> : <span aria-hidden="true">✨</span>}
          {parsing ? 'Rozpoznawanie…' : 'Wypełnij formularz'}
        </button>
        <span className="text-xs text-slate-400 tabular-nums">
          {text.length}/{PARSE_TEXT_MAX_LENGTH}
        </span>
      </div>

      {error && (
        <p role="alert" className={alert}>
          {error}
        </p>
      )}

      {result && (
        <div role="status" className="space-y-1 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
          <p className="flex flex-wrap items-center gap-2">
            {result.source === 'ai' ? (
              <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">AI</span>
            ) : (
              <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700">tryb demo</span>
            )}
            <span>Formularz wypełniony — sprawdź pola i kliknij „Dodaj trasę”.</span>
          </p>
          {missing.length > 0 && (
            <p className="text-amber-800">Uzupełnij: {missing.map((field) => MISSING_LABELS[field]).join(', ')}.</p>
          )}
          {result.source === 'demo' && (
            <p className="text-xs text-slate-500">
              Tryb demo rozpoznaje proste zdania typu „z A do B” i nie odmienia nazw — popraw je w razie potrzeby.
            </p>
          )}
        </div>
      )}
    </form>
  )
}
