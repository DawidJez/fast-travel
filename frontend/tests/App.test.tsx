import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../src/api/client'
import App from '../src/App'
import { makeComparison, makeTrip } from './fixtures'

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return {
    ...actual,
    api: {
      listTrips: vi.fn(), createTrip: vi.fn(), updateTrip: vi.fn(), deleteTrip: vi.fn(), getComparison: vi.fn(), parseTrip: vi.fn(),
    },
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
const select = (name: string) => fireEvent.click(within(item(name)).getByRole('button', { name: new RegExp(`^${name}`) }))

describe('App', () => {
  it('loads and shows the trips', async () => {
    render(<App />)
    expect(screen.getByText('Ładowanie tras…')).toBeInTheDocument()
    expect(await screen.findByText('Praca')).toBeInTheDocument()
    expect(screen.getByText('Szkoła')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'OpenStreetMap contributors' })).toHaveAttribute(
      'href', 'https://www.openstreetmap.org/copyright',
    )
    expect(screen.getByRole('contentinfo')).toHaveTextContent('Geokodowanie: © OpenStreetMap contributors')
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

    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
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
    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(screen.getByRole('heading', { name: 'Nowa trasa' })).toBeInTheDocument()
  })

  it('deletes after confirmation', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockResolvedValue(undefined)
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Usuń/ }))

    expect(confirm).toHaveBeenCalledWith('Usunąć trasę „Praca”?')
    await waitFor(() => expect(screen.queryByText('Praca')).not.toBeInTheDocument())
    expect(api.deleteTrip).toHaveBeenCalledWith(1)
  })

  it('does nothing when deletion is not confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Usuń/ }))
    expect(api.deleteTrip).not.toHaveBeenCalled()
    expect(screen.getByText('Praca')).toBeInTheDocument()
  })

  it('deleting the trip being edited leaves edit mode', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockResolvedValue(undefined)
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Usuń/ }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Nowa trasa' })).toBeInTheDocument())
  })

  it('shows a delete error and keeps the trip', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.deleteTrip).mockRejectedValue(new ApiError(500, 'Błąd serwera (HTTP 500).'))
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Usuń/ }))
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

    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
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

    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Usuń/ }))

    expect(await screen.findByText('Wybierz trasę z listy, aby zobaczyć porównanie.')).toBeInTheDocument()
  })

  it('on a narrow screen scrolls to the comparison and to the form', async () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query === '(max-width: 1023px)' }))
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    try {
      render(<App />)
      await screen.findByText('Praca')
      select('Praca')
      expect(scroll).toHaveBeenCalledTimes(1)
      expect(scroll.mock.contexts[0]).toBe(screen.getByRole('region', { name: 'Porównanie' }))
      fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
      expect(scroll).toHaveBeenCalledTimes(2)
    } finally {
      delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView
      vi.unstubAllGlobals()
    }
  })

  it('does not scroll on a wide screen', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    try {
      render(<App />)
      await screen.findByText('Praca')
      select('Praca')
      expect(scroll).not.toHaveBeenCalled()
    } finally {
      delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView
      vi.unstubAllGlobals()
    }
  })

  // --- late answers (a save or load that finishes after the user moved on) ---

  it('a slow save does not cancel the edit of another trip started meanwhile', async () => {
    let resolvePut!: (trip: typeof WORK) => void
    vi.mocked(api.updateTrip).mockReturnValue(new Promise((r) => (resolvePut = r)))
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
    fireEvent.change(screen.getByLabelText('Nazwa'), { target: { value: 'Praca (nowa)' } })
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zmiany' }))
    fireEvent.click(within(item('Szkoła')).getByRole('button', { name: /^Edytuj/ }))
    fireEvent.change(screen.getByLabelText('Notatka'), { target: { value: 'niezapisane' } })

    resolvePut({ ...WORK, name: 'Praca (nowa)' })

    expect(await screen.findByText('Praca (nowa)')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Edytuj trasę' })).toBeInTheDocument()
    expect(screen.getByLabelText('Nazwa')).toHaveValue('Szkoła')
    expect(screen.getByLabelText('Notatka')).toHaveValue('niezapisane')
  })

  it('a slow create does not cancel an edit started meanwhile', async () => {
    let resolvePost!: (trip: typeof WORK) => void
    vi.mocked(api.createTrip).mockReturnValue(new Promise((r) => (resolvePost = r)))
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.change(screen.getByLabelText('Nazwa'), { target: { value: 'Basen' } })
    fireEvent.change(screen.getByLabelText('Skąd'), { target: { value: 'a' } })
    fireEvent.change(screen.getByLabelText('Dokąd'), { target: { value: 'b' } })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))
    fireEvent.click(within(item('Szkoła')).getByRole('button', { name: /^Edytuj/ }))

    resolvePost(makeTrip({ id: 3, name: 'Basen' }))

    expect(await screen.findByText('Basen')).toBeInTheDocument()
    expect(screen.getByLabelText('Nazwa')).toHaveValue('Szkoła')
  })

  it('a slow edit answered after the trip was deleted does not bring it back', async () => {
    let resolvePut!: (trip: typeof WORK) => void
    vi.mocked(api.updateTrip).mockReturnValue(new Promise((r) => (resolvePut = r)))
    vi.mocked(api.deleteTrip).mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<App />)
    await screen.findByText('Praca')

    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Edytuj/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zmiany' }))
    fireEvent.click(within(item('Praca')).getByRole('button', { name: /^Usuń/ }))
    await waitFor(() => expect(screen.queryByText('Praca')).not.toBeInTheDocument())

    resolvePut({ ...WORK, name: 'Praca' })

    await waitFor(() => expect(api.updateTrip).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText('Praca')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('after a failed list load, a successful create reloads the list', async () => {
    vi.mocked(api.listTrips)
      .mockRejectedValueOnce(new ApiError(0, 'Brak połączenia z serwerem'))
      .mockResolvedValueOnce([makeTrip({ id: 3, name: 'Basen' }), WORK, SCHOOL])
    vi.mocked(api.createTrip).mockResolvedValue(makeTrip({ id: 3, name: 'Basen' }))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Brak połączenia z serwerem')

    fireEvent.change(screen.getByLabelText('Nazwa'), { target: { value: 'Basen' } })
    fireEvent.change(screen.getByLabelText('Skąd'), { target: { value: 'a' } })
    fireEvent.change(screen.getByLabelText('Dokąd'), { target: { value: 'b' } })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))

    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(3))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(api.listTrips).toHaveBeenCalledTimes(2)
  })

  it('a late comparison of the previously selected trip is not shown', async () => {
    let resolveFirst!: (c: ReturnType<typeof makeComparison>) => void
    vi.mocked(api.getComparison)
      .mockReturnValueOnce(new Promise((r) => (resolveFirst = r)))
      .mockResolvedValueOnce(makeComparison({ trip_id: 2, destination: 'Szkoła nr 5' }))
    render(<App />)
    await screen.findByText('Praca')

    select('Praca')
    select('Szkoła')
    expect(await screen.findByText(/→ Szkoła nr 5/)).toBeInTheDocument()

    resolveFirst(makeComparison({ trip_id: 1, destination: 'Stara odpowiedź' }))

    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText(/Stara odpowiedź/)).not.toBeInTheDocument()
    expect(screen.getByText(/→ Szkoła nr 5/)).toBeInTheDocument()
  })

  // --- AI parser -> form ---

  const PARSED = { name: 'Do pracy', origin: 'Oliwa', destination: 'Politechnika Gdańska', source: 'ai' as const }

  async function parse(text: string) {
    fireEvent.change(screen.getByLabelText('Opisz trasę własnymi słowami'), { target: { value: text } })
    fireEvent.click(screen.getByRole('button', { name: /Wypełnij formularz/ }))
  }

  it('the parser fills the new-trip form, which the user can correct and save', async () => {
    vi.mocked(api.parseTrip).mockResolvedValue(PARSED)
    vi.mocked(api.createTrip).mockResolvedValue(makeTrip({ id: 3, name: 'Do pracy (popr.)' }))
    render(<App />)
    await screen.findByText('Praca')

    await parse('Do pracy: z Oliwy na Politechnikę')

    await waitFor(() => expect(screen.getByLabelText('Skąd')).toHaveValue('Oliwa'))
    expect(screen.getByLabelText('Dokąd')).toHaveValue('Politechnika Gdańska')
    fireEvent.change(screen.getByLabelText('Nazwa'), { target: { value: 'Do pracy (popr.)' } })
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj trasę' }))

    await waitFor(() => expect(api.createTrip).toHaveBeenCalledWith({
      name: 'Do pracy (popr.)', origin: 'Oliwa', destination: 'Politechnika Gdańska', notes: null,
    }))
    await waitFor(() => expect(screen.getByLabelText('Skąd')).toHaveValue(''))
  })

  it('nothing is saved until the user clicks "Dodaj trasę"', async () => {
    vi.mocked(api.parseTrip).mockResolvedValue(PARSED)
    render(<App />)
    await screen.findByText('Praca')
    await parse('z Oliwy na Politechnikę')
    await waitFor(() => expect(screen.getByLabelText('Skąd')).toHaveValue('Oliwa'))
    expect(api.createTrip).not.toHaveBeenCalled()
  })

  it('parsing while editing switches to a new trip', async () => {
    vi.mocked(api.parseTrip).mockResolvedValue(PARSED)
    render(<App />)
    await screen.findByText('Praca')
    fireEvent.click(within(item('Szkoła')).getByRole('button', { name: /^Edytuj/ }))

    await parse('z Oliwy na Politechnikę')

    expect(screen.getByRole('heading', { name: 'Nowa trasa' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Skąd')).toHaveValue('Oliwa'))
  })

  it('a slow parse does not cancel an edit started meanwhile', async () => {
    let resolve!: (p: typeof PARSED) => void
    vi.mocked(api.parseTrip).mockReturnValue(new Promise((r) => (resolve = r)))
    render(<App />)
    await screen.findByText('Praca')

    await parse('z Oliwy na Politechnikę')
    fireEvent.click(within(item('Szkoła')).getByRole('button', { name: /^Edytuj/ }))
    fireEvent.change(screen.getByLabelText('Notatka'), { target: { value: 'niezapisane' } })
    resolve(PARSED)

    expect(await screen.findByText(/Formularz wypełniony/)).toBeInTheDocument()
    expect(screen.getByLabelText('Nazwa')).toHaveValue('Szkoła')
    expect(screen.getByLabelText('Notatka')).toHaveValue('niezapisane')
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(screen.getByLabelText('Skąd')).toHaveValue('Oliwa') // waiting in the new-trip form
  })
})
