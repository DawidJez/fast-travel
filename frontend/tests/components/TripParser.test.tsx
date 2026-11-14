import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, type ParsedTrip } from '../../src/api/client'
import TripParser from '../../src/components/TripParser'

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>()
  return { ...actual, api: { parseTrip: vi.fn() } }
})

const AI: ParsedTrip = { name: 'Do pracy', origin: 'Oliwa', destination: 'Politechnika Gdańska', source: 'ai' }

beforeEach(() => vi.clearAllMocks())

function renderParser() {
  const handlers = { onStart: vi.fn(), onParsed: vi.fn() }
  render(<TripParser {...handlers} />)
  return handlers
}

const describeTrip = (text: string) =>
  fireEvent.change(screen.getByLabelText('Opisz trasę własnymi słowami'), { target: { value: text } })
const submit = () => fireEvent.click(screen.getByRole('button', { name: /Wypełnij formularz/ }))

describe('TripParser', () => {
  it('sends the text, then reports the result with an AI badge', async () => {
    vi.mocked(api.parseTrip).mockResolvedValue(AI)
    const { onStart, onParsed } = renderParser()

    describeTrip('Do pracy: rano z Oliwy na Politechnikę Gdańską')
    submit()

    expect(onStart).toHaveBeenCalledOnce()
    await waitFor(() => expect(onParsed).toHaveBeenCalledWith(AI))
    expect(api.parseTrip).toHaveBeenCalledWith('Do pracy: rano z Oliwy na Politechnikę Gdańską')
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('AI')
    expect(status).toHaveTextContent('Formularz wypełniony')
    expect(status).not.toHaveTextContent('tryb demo')
  })

  it('marks a demo result and explains its limits', async () => {
    vi.mocked(api.parseTrip).mockResolvedValue({ ...AI, source: 'demo' })
    renderParser()
    describeTrip('z Oliwa do Wrzeszcz')
    submit()
    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('tryb demo')
    expect(status).toHaveTextContent('rozpoznaje proste zdania')
  })

  it('lists fields the text did not give', async () => {
    vi.mocked(api.parseTrip).mockResolvedValue({ name: null, origin: null, destination: 'Sopot', source: 'ai' })
    renderParser()
    describeTrip('do Sopotu')
    submit()
    expect(await screen.findByText('Uzupełnij: Skąd.')).toBeInTheDocument()
  })

  it('shows a spinner and blocks the field while waiting', async () => {
    let resolve!: (parsed: ParsedTrip) => void
    vi.mocked(api.parseTrip).mockReturnValue(new Promise((r) => (resolve = r)))
    renderParser()
    describeTrip('z Oliwa do Wrzeszcz')
    submit()

    expect(screen.getByRole('button', { name: /Rozpoznawanie…/ })).toBeDisabled()
    expect(screen.getByLabelText('Opisz trasę własnymi słowami')).toBeDisabled()
    resolve(AI)
    await waitFor(() => expect(screen.getByRole('button', { name: /Wypełnij formularz/ })).toBeEnabled())
  })

  it('shows a backend error and does not fill the form', async () => {
    vi.mocked(api.parseTrip).mockRejectedValue(new ApiError(422, 'Nie rozpoznano trasy.'))
    const { onParsed } = renderParser()
    describeTrip('jutro rano')
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie rozpoznano trasy.')
    expect(onParsed).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('clears the previous result when asking again', async () => {
    vi.mocked(api.parseTrip).mockResolvedValueOnce(AI).mockRejectedValueOnce(new ApiError(503, 'x'))
    renderParser()
    describeTrip('z Oliwa do Wrzeszcz')
    submit()
    await screen.findByRole('status')
    submit()
    await screen.findByRole('alert')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('needs some text and limits it like the backend', () => {
    renderParser()
    expect(screen.getByRole('button', { name: /Wypełnij formularz/ })).toBeDisabled()
    describeTrip('   ')
    expect(screen.getByRole('button', { name: /Wypełnij formularz/ })).toBeDisabled()
    expect(screen.getByLabelText('Opisz trasę własnymi słowami')).toHaveAttribute('maxlength', '500')
    describeTrip('abc')
    expect(screen.getByText('3/500')).toBeInTheDocument()
  })
})
