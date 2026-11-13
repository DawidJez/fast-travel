import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import App from './App'
import { makeComparison, makeTrip } from './test/fixtures'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    api: { listTrips: vi.fn(), createTrip: vi.fn(), updateTrip: vi.fn(), deleteTrip: vi.fn(), getComparison: vi.fn() },
  }
})

const WORK = makeTrip({ id: 1, name: 'Praca' })
const SCHOOL = makeTrip({ id: 2, name: 'Szkoła' })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.listTrips).mockResolvedValue([WORK, SCHOOL])
  vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
})
afterEach(() => vi.restoreAllMocks())

const item = (name: string) => screen.getByText(name).closest('li') as HTMLElement
const select = (name: string) => fireEvent.click(within(item(name)).getByRole('button', { name: new RegExp(name) }))

describe('App', () => {
  it('loads and shows the trips', async () => {
    render(<App />)
    expect(screen.getByText('Ładowanie tras…')).toBeInTheDocument()
    expect(await screen.findByText('Praca')).toBeInTheDocument()
    expect(screen.getByText('Szkoła')).toBeInTheDocument()
    expect(screen.getByText(/© OpenStreetMap contributors/)).toBeInTheDocument()
  })

  it('shows a load error and retries', async () => {
    vi.mocked(api.listTrips).mockRejectedValueOnce(new ApiError(0, 'Brak połączenia z serwerem'))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Brak połączenia z serwerem')
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(await screen.findByText('Praca')).toBeInTheDocument()
    expect(api.listTrips).toHaveBeenCalledTimes(2)
  })

  it('adds a new trip at the top of the list', async () => {
    const created = makeTrip({ id: 3, name: 'Basen' })
    vi.mocked(api.createTrip).mockResolvedValue(created)
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.change(screen.getByLabelText('Nazwa'), { target: { value: 'Basen' } })
    fireEvent.change(screen.getByLabelText('Skąd'), { target: { value: 'a' } })
    fireEvent.change(screen.getByLabelText('Dokąd'), { target: { value: 'b' } })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))

    await waitFor(() => expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('Basen'))
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('edits a trip in place and returns to add mode', async () => {
    vi.mocked(api.updateTrip).mockResolvedValue({ ...WORK, name: 'Praca (nowa)' })
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Edytuj' }))
    expect(screen.getByLabelText('Nazwa')).toHaveValue('Praca')
    fireEvent.change(screen.getByLabelText('Nazwa'), { target: { value: 'Praca (nowa)' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zmiany' }))

    await waitFor(() => expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('Praca (nowa)'))
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Dodaj trasę' })).toBeInTheDocument()
    expect(screen.getByLabelText('Nazwa')).toHaveValue('')
  })

  it('cancel leaves edit mode', async () => {
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Edytuj' }))
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(screen.getByRole('heading', { name: 'Nowa trasa' })).toBeInTheDocument()
  })

  it('deletes after confirmation', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockResolvedValue(undefined)
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Usuń' }))

    expect(confirm).toHaveBeenCalledWith('Usunąć trasę „Praca”?')
    await waitFor(() => expect(screen.queryByText('Praca')).not.toBeInTheDocument())
    expect(api.deleteTrip).toHaveBeenCalledWith(1)
  })

  it('does nothing when deletion is not confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Usuń' }))
    expect(api.deleteTrip).not.toHaveBeenCalled()
    expect(screen.getByText('Praca')).toBeInTheDocument()
  })

  it('deleting the trip being edited leaves edit mode', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockResolvedValue(undefined)
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Edytuj' }))
    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Usuń' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Nowa trasa' })).toBeInTheDocument())
  })

  it('shows a delete error and keeps the trip', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockRejectedValue(new ApiError(500, 'Błąd serwera (HTTP 500).'))
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Usuń' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Błąd serwera (HTTP 500).')
    expect(screen.getByText('Praca')).toBeInTheDocument()
  })

  it('shows a hint until a trip is selected, then its comparison', async () => {
    render(<App />)
    await screen.findByText('Praca')
    expect(screen.getByText('Wybierz trasę z listy, aby zobaczyć porównanie.')).toBeInTheDocument()

    select('Praca')

    expect(await screen.findByText('Polecamy: Rower')).toBeInTheDocument()
    expect(api.getComparison).toHaveBeenCalledWith(1)
  })

  it('reloads the comparison when another trip is selected', async () => {
    render(<App />)
    await screen.findByText('Praca')
    select('Praca')
    await screen.findByText('Polecamy: Rower')
    select('Szkoła')
    await waitFor(() => expect(api.getComparison).toHaveBeenLastCalledWith(2))
  })

  it('reloads the comparison after the selected trip places are edited', async () => {
    vi.mocked(api.updateTrip).mockResolvedValue({ ...WORK, destination: 'Sopot' })
    render(<App />)
    await screen.findByText('Praca')
    select('Praca')
    await screen.findByText('Polecamy: Rower')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Edytuj' }))
    fireEvent.change(screen.getByLabelText('Dokąd'), { target: { value: 'Sopot' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zmiany' }))

    await waitFor(() => expect(api.getComparison).toHaveBeenCalledTimes(2))
  })

  it('deleting the selected trip hides its comparison', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockResolvedValue(undefined)
    render(<App />)
    await screen.findByText('Praca')
    select('Praca')
    await screen.findByText('Polecamy: Rower')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: 'Usuń' }))

    expect(await screen.findByText('Wybierz trasę z listy, aby zobaczyć porównanie.')).toBeInTheDocument()
  })
})
