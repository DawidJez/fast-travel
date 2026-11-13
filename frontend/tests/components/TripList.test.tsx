import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import TripList from '../../src/components/TripList'
import { makeTrip } from '../fixtures'

function renderList(props: Partial<Parameters<typeof TripList>[0]> = {}) {
  const handlers = { onRetry: vi.fn(), onSelect: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn() }
  render(<TripList trips={[]} loading={false} error={null} actionError={null} selectedId={null} {...handlers} {...props} />)
  return handlers
}

describe('TripList', () => {
  it('shows loading state', () => {
    renderList({ loading: true })
    expect(screen.getByText('Ładowanie tras…')).toBeInTheDocument()
  })

  it('shows empty state', () => {
    renderList()
    expect(screen.getByText(/Brak zapisanych tras/)).toBeInTheDocument()
  })

  it('shows load error with retry', () => {
    const { onRetry } = renderList({ error: 'Brak połączenia z serwerem' })
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać tras: Brak połączenia z serwerem')
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('renders trips with notes and action buttons', () => {
    const trip = makeTrip({ notes: 'rano' })
    const { onEdit, onDelete } = renderList({ trips: [trip, makeTrip({ id: 2, name: 'Szkoła' })] })
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('Gdańsk Wrzeszcz → Gdańsk Oliwa')
    expect(screen.getByText('rano')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Edytuj' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Usuń' })[0])
    expect(onEdit).toHaveBeenCalledWith(trip)
    expect(onDelete).toHaveBeenCalledWith(trip)
  })

  it('shows action error above the list', () => {
    renderList({ trips: [makeTrip()], actionError: 'Nie znaleziono podróży' })
    expect(screen.getByRole('alert')).toHaveTextContent('Nie znaleziono podróży')
    expect(screen.getByRole('listitem')).toBeInTheDocument()
  })

  it('selects a trip and marks the selected one', () => {
    const trip = makeTrip({ id: 2, name: 'Szkoła' })
    const { onSelect } = renderList({ trips: [makeTrip(), trip], selectedId: 2 })
    const select = screen.getByRole('button', { name: /Szkoła/ })
    expect(select).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Praca/ })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(select)
    expect(onSelect).toHaveBeenCalledWith(trip)
  })
})
