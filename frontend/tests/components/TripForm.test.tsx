import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../../src/api/client'
import TripForm from '../../src/components/TripForm'
import { makeTrip } from '../fixtures'

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>()
  return { ...actual, api: { ...actual.api, createTrip: vi.fn(), updateTrip: vi.fn() } }
})

const type = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

function fill(values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) type(label, value)
}

beforeEach(() => vi.clearAllMocks())

describe('TripForm — add', () => {
  it('POSTs the values, empty notes as null, then clears the form', async () => {
    const saved = makeTrip({ id: 9 })
    vi.mocked(api.createTrip).mockResolvedValue(saved)
    const onSaved = vi.fn()
    render(<TripForm trip={null} onSaved={onSaved} onCancel={vi.fn()} />)

    fill({ Nazwa: 'Praca', Skąd: 'Gdańsk Wrzeszcz', Dokąd: 'Gdańsk Oliwa', Notatka: '   ' })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved, true))
    expect(api.createTrip).toHaveBeenCalledWith({
      name: 'Praca', origin: 'Gdańsk Wrzeszcz', destination: 'Gdańsk Oliwa', notes: null,
    })
    expect(screen.getByLabelText('Nazwa')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'Anuluj' })).not.toBeInTheDocument()
  })

  it('shows a backend error next to the form and keeps the values', async () => {
    vi.mocked(api.createTrip).mockRejectedValue(new ApiError(422, 'Nie znaleziono miejsca „Xyz”.'))
    const onSaved = vi.fn()
    render(<TripForm trip={null} onSaved={onSaved} onCancel={vi.fn()} />)

    fill({ Nazwa: 'Praca', Skąd: 'Xyz', Dokąd: 'Sopot' })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Nie znaleziono miejsca „Xyz”.')
    expect(screen.getByLabelText('Skąd')).toHaveValue('Xyz')
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('shows a generic message for unexpected errors', async () => {
    vi.mocked(api.createTrip).mockRejectedValue(new Error('bug'))
    render(<TripForm trip={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    fill({ Nazwa: 'a', Skąd: 'b', Dokąd: 'c' })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Wystąpił nieoczekiwany błąd.')
  })

  it('disables the form while saving', async () => {
    let resolve!: (trip: ReturnType<typeof makeTrip>) => void
    vi.mocked(api.createTrip).mockReturnValue(new Promise((r) => (resolve = r)))
    render(<TripForm trip={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    fill({ Nazwa: 'a', Skąd: 'b', Dokąd: 'c' })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))

    expect(await screen.findByRole('button', { name: 'Zapisywanie…' })).toBeDisabled()
    expect(screen.getByLabelText('Nazwa')).toBeDisabled()
    resolve(makeTrip())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Dodaj trasę' })).toBeEnabled())
  })

  it('requires name, origin and destination and limits lengths like the backend', () => {
    render(<TripForm trip={null} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByLabelText('Nazwa')).toHaveAttribute('maxlength', '100')
    for (const label of ['Nazwa', 'Skąd', 'Dokąd']) expect(screen.getByLabelText(label)).toBeRequired()
    expect(screen.getByLabelText('Skąd')).toHaveAttribute('maxlength', '200')
    expect(screen.getByLabelText('Notatka')).not.toBeRequired()
    expect(screen.getByLabelText('Notatka')).toHaveAttribute('maxlength', '1000')
  })
})

describe('TripForm — edit', () => {
  it('starts from the trip values and PUTs the changes', async () => {
    const trip = makeTrip({ id: 4, notes: 'rano' })
    const saved = { ...trip, destination: 'Sopot' }
    vi.mocked(api.updateTrip).mockResolvedValue(saved)
    const onSaved = vi.fn()
    render(<TripForm trip={trip} onSaved={onSaved} onCancel={vi.fn()} />)

    expect(screen.getByRole('heading')).toHaveTextContent('Edytuj trasę')
    expect(screen.getByLabelText('Notatka')).toHaveValue('rano')
    type('Dokąd', 'Sopot')
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zmiany' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved, false))
    expect(api.updateTrip).toHaveBeenCalledWith(4, {
      name: 'Praca', origin: 'Gdańsk Wrzeszcz', destination: 'Sopot', notes: 'rano',
    })
    expect(api.createTrip).not.toHaveBeenCalled()
  })

  it('clearing the notes sends null', async () => {
    vi.mocked(api.updateTrip).mockResolvedValue(makeTrip())
    render(<TripForm trip={makeTrip({ notes: 'rano' })} onSaved={vi.fn()} onCancel={vi.fn()} />)
    type('Notatka', '')
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zmiany' }))
    await waitFor(() => expect(api.updateTrip).toHaveBeenCalledWith(1, expect.objectContaining({ notes: null })))
  })

  it('cancel calls onCancel', () => {
    const onCancel = vi.fn()
    render(<TripForm trip={makeTrip()} onSaved={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})

describe('TripForm — prefill from the AI parser', () => {
  it('starts a new trip from the parsed fields; missing ones stay empty', () => {
    const prefill = { name: null, origin: 'Oliwa', destination: 'Sopot', source: 'ai' as const }
    render(<TripForm trip={null} prefill={prefill} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByLabelText('Nazwa')).toHaveValue('')
    expect(screen.getByLabelText('Skąd')).toHaveValue('Oliwa')
    expect(screen.getByLabelText('Dokąd')).toHaveValue('Sopot')
    expect(screen.getByLabelText('Notatka')).toHaveValue('')
  })

  it('ignores the prefill when editing a trip', () => {
    const prefill = { name: 'X', origin: 'Y', destination: 'Z', source: 'ai' as const }
    render(<TripForm trip={makeTrip()} prefill={prefill} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByLabelText('Nazwa')).toHaveValue('Praca')
  })
})
