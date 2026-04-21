import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VirtualTable } from '../components/ui/virtual-table'

describe('VirtualTable', () => {
  const items = [
    { id: 1, name: 'Alpha', score: 10 },
    { id: 2, name: 'Bravo', score: 20 },
    { id: 3, name: 'Charlie', score: 30 },
  ]

  const columns = [
    { key: 'name', header: 'Name', width: '1fr', render: (item) => item.name },
    { key: 'score', header: 'Score', width: '100px', render: (item) => String(item.score) },
  ]

  it('renders all column headers', () => {
    render(<VirtualTable items={items} columns={columns} getItemKey={(item) => item.id} />)

    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()
  })

  it('renders all 3 rows from items array', () => {
    render(<VirtualTable items={items} columns={columns} getItemKey={(item) => item.id} />)

    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Bravo')).toBeInTheDocument()
    expect(screen.getByText('Charlie')).toBeInTheDocument()
  })

  it('calls column render function with item and index for each row', () => {
    const nameRender = vi.fn((item) => item.name)
    const columnsWithMock = [
      { key: 'name', header: 'Name', width: '1fr', render: nameRender },
      { key: 'score', header: 'Score', width: '100px', render: (item) => String(item.score) },
    ]

    render(<VirtualTable items={items} columns={columnsWithMock} getItemKey={(item) => item.id} />)

    expect(nameRender.mock.calls.length).toBeGreaterThanOrEqual(items.length)

    const seenItemIds = new Set()
    for (const [item, index] of nameRender.mock.calls) {
      seenItemIds.add(item.id)
      expect(items[index]).toBe(item)
    }
    expect(seenItemIds).toEqual(new Set([1, 2, 3]))
  })

  it('renders emptyContent when items is empty and not loading', () => {
    render(
      <VirtualTable
        items={[]}
        columns={columns}
        getItemKey={(item) => item.id}
        loading={false}
        emptyContent={<div>No data</div>}
      />,
    )

    expect(screen.getByText('No data')).toBeInTheDocument()
  })

  it('renders loadingContent when loading is true and items is empty', () => {
    render(
      <VirtualTable
        items={[]}
        columns={columns}
        getItemKey={(item) => item.id}
        loading
        loadingContent={<div>Loading...</div>}
      />,
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('uses getItemKey to derive stable row keys', () => {
    const getItemKey = vi.fn((item) => `row-${item.id}`)

    render(<VirtualTable items={items} columns={columns} getItemKey={getItemKey} />)

    expect(getItemKey).toHaveBeenCalled()
    expect(getItemKey.mock.calls.length).toBeGreaterThanOrEqual(items.length)
    expect(getItemKey).toHaveBeenCalledWith(items[0])
    expect(getItemKey).toHaveBeenCalledWith(items[1])
    expect(getItemKey).toHaveBeenCalledWith(items[2])
  })

  it('invokes onRowClick with item when row is clicked', () => {
    const onRowClick = vi.fn()

    render(
      <VirtualTable
        items={items}
        columns={columns}
        getItemKey={(item) => item.id}
        onRowClick={onRowClick}
      />,
    )

    fireEvent.click(screen.getByText('Alpha').closest('[data-row]'))

    expect(onRowClick).toHaveBeenCalledTimes(1)
    expect(onRowClick).toHaveBeenCalledWith(items[0])
  })

  it('applies rowClassName function result to row container', () => {
    render(
      <VirtualTable
        items={items}
        columns={columns}
        getItemKey={(item) => item.id}
        rowClassName={(item) => (item.id === 2 ? 'highlighted' : '')}
      />,
    )

    expect(screen.getByText('Bravo').closest('[data-row]')).toHaveClass('highlighted')
    expect(screen.getByText('Alpha').closest('[data-row]')).not.toHaveClass('highlighted')
  })

  it('renders header and body with matching column count', () => {
    render(<VirtualTable items={items} columns={columns} getItemKey={(item) => item.id} />)

    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()

    const alphaRow = screen.getByText('Alpha').closest('[data-row]')

    expect(alphaRow.querySelectorAll('[data-cell]')).toHaveLength(columns.length)
  })
})
