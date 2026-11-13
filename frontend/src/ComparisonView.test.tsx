import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import ComparisonView from './ComparisonView'
import { makeComparison } from './test/fixtures'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return { ...actual, api: { getComparison: vi.fn() } }
})

beforeEach(() => vi.clearAllMocks())

const card = (label: string) => screen.getByRole('listitem', { name: label })

describe('ComparisonView', () => {
  it('loads the comparison of the given trip', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
    render(<ComparisonView tripId={7} />)
    expect(screen.getByText('Liczenie porównania…')).toBeInTheDocument()
    expect(await screen.findByText('Gdańsk Wrzeszcz → Gdańsk Oliwa')).toBeInTheDocument()
    expect(api.getComparison).toHaveBeenCalledWith(7)
    expect(screen.getByText(/^W linii prostej: 4,2 km · stan na \d{2}:\d{2}$/)).toBeInTheDocument()
  })

  it('shows four mode cards with time, cost, CO2 and distance', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Gdańsk Wrzeszcz → Gdańsk Oliwa')

    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    const car = card('Samochód')
    expect(car).toHaveTextContent('ok. 17 min')
    expect(car).toHaveTextContent('6,33 zł')
    expect(car).toHaveTextContent('919 g')
    expect(car).toHaveTextContent('5,5 km')
    expect(card('Pieszo')).toHaveTextContent('ok. 1 h 00 min')
  })

  it('highlights the recommended mode with its reason', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Polecamy: Rower')

    expect(screen.getByText(/Rower \(ok\. 20 min\) zamiast samochodu/)).toBeInTheDocument()
    expect(within(card('Rower')).getByText('polecane')).toBeInTheDocument()
    expect(within(card('Samochód')).queryByText('polecane')).not.toBeInTheDocument()
  })

  it('marks public transport as an estimate with its note', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Polecamy: Rower')

    const pt = card('Komunikacja miejska')
    expect(within(pt).getByText('szacunek')).toBeInTheDocument()
    expect(pt).toHaveTextContent('bez rozkładów jazdy i kolei (np. SKM)')
    expect(within(card('Samochód')).queryByText('szacunek')).not.toBeInTheDocument()
  })

  it('summarises the weather', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
    render(<ComparisonView tripId={1} />)
    expect(await screen.findByText('Pogoda teraz w punkcie startu: 3,8 °C, opady 0,0 mm, wiatr 10 km/h.')).toBeInTheDocument()
  })

  it('says when weather is unavailable', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison({ weather: null }))
    render(<ComparisonView tripId={1} />)
    expect(await screen.findByText(/Brak danych pogodowych/)).toBeInTheDocument()
  })

  it('notes the rush-hour penalty on the car card only in peak', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison({ car_peak: true }))
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Polecamy: Rower')
    expect(card('Samochód')).toHaveTextContent('Godziny szczytu')
    expect(card('Rower')).not.toHaveTextContent('Godziny szczytu')
  })

  it('has no rush-hour note off peak', async () => {
    vi.mocked(api.getComparison).mockResolvedValue(makeComparison())
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Polecamy: Rower')
    expect(screen.queryByText(/Godziny szczytu/)).not.toBeInTheDocument()
  })

  it('shows an error and retries', async () => {
    vi.mocked(api.getComparison)
      .mockRejectedValueOnce(new ApiError(404, 'Nie znaleziono podróży (mogła zostać usunięta).'))
      .mockResolvedValueOnce(makeComparison())
    render(<ComparisonView tripId={1} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się pobrać porównania: Nie znaleziono podróży')
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(await screen.findByText('Polecamy: Rower')).toBeInTheDocument()
    expect(api.getComparison).toHaveBeenCalledTimes(2)
  })

  it('shows a spinner while loading', () => {
    vi.mocked(api.getComparison).mockReturnValue(new Promise(() => {}))
    render(<ComparisonView tripId={1} />)
    expect(screen.getByRole('status')).toHaveTextContent('Liczenie porównania…')
    expect(screen.queryByRole('button', { name: /Odśwież/ })).not.toBeInTheDocument()
  })

  it('refresh fetches again and keeps the old figures meanwhile', async () => {
    let resolve!: (c: ReturnType<typeof makeComparison>) => void
    vi.mocked(api.getComparison)
      .mockResolvedValueOnce(makeComparison())
      .mockReturnValueOnce(new Promise((r) => (resolve = r)))
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Polecamy: Rower')

    fireEvent.click(screen.getByRole('button', { name: /Odśwież/ }))

    expect(screen.getByRole('button', { name: /Przeliczanie…/ })).toBeDisabled()
    expect(screen.getByText('Polecamy: Rower')).toBeInTheDocument()
    resolve(makeComparison({ recommendation: { mode: 'car', reason: 'Pada.' } }))
    expect(await screen.findByText('Polecamy: Samochód')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Odśwież/ })).toBeEnabled()
    expect(api.getComparison).toHaveBeenCalledTimes(2)
  })

  it('a failed refresh shows the error but keeps the last figures', async () => {
    vi.mocked(api.getComparison)
      .mockResolvedValueOnce(makeComparison())
      .mockRejectedValueOnce(new ApiError(0, 'Brak połączenia z serwerem'))
    render(<ComparisonView tripId={1} />)
    await screen.findByText('Polecamy: Rower')

    fireEvent.click(screen.getByRole('button', { name: /Odśwież/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Brak połączenia z serwerem')
    expect(screen.getByText('Polecamy: Rower')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: /Odśwież/ })).toBeEnabled())
  })
})
