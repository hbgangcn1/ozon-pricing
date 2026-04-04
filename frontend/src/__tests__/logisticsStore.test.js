import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useLogisticsStore } from '../stores/logisticsStore'

describe('logisticsStore.js', () => {
  const initialState = useLogisticsStore.getState()
  
  beforeEach(() => {
    useLogisticsStore.setState(initialState, true)
    vi.clearAllMocks()
  })

  describe('Initial state', () => {
    it('has correct initial state', () => {
      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual([])
      expect(state.loading).toBe(false)
      expect(state.error).toBeNull()
    })
  })

  describe('setLogistics()', () => {
    it('sets the logistics array', () => {
      const mockLogistics = [{ id: 1, provider: 'DHL' }, { id: 2, provider: 'FedEx' }]
      useLogisticsStore.getState().setLogistics(mockLogistics)
      
      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual(mockLogistics)
    })
  })

  describe('setLoading()', () => {
    it('updates loading state', () => {
      useLogisticsStore.getState().setLoading(true)
      expect(useLogisticsStore.getState().loading).toBe(true)

      useLogisticsStore.getState().setLoading(false)
      expect(useLogisticsStore.getState().loading).toBe(false)
    })
  })

  describe('setError()', () => {
    it('updates error state', () => {
      const errorMsg = 'Failed to load logistics'
      useLogisticsStore.getState().setError(errorMsg)
      expect(useLogisticsStore.getState().error).toBe(errorMsg)

      useLogisticsStore.getState().setError(null)
      expect(useLogisticsStore.getState().error).toBeNull()
    })
  })

  describe('addLogistics()', () => {
    it('appends a new logistics item to the existing array', () => {
      const initialLogistics = [{ id: 1, provider: 'DHL' }]
      useLogisticsStore.setState({ logistics: initialLogistics })

      const newItem = { id: 2, provider: 'FedEx' }
      useLogisticsStore.getState().addLogistics(newItem)

      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual([...initialLogistics, newItem])
    })

    it('works when logistics array is empty', () => {
      const newItem = { id: 1, provider: 'DHL' }
      useLogisticsStore.getState().addLogistics(newItem)

      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual([newItem])
    })
  })

  describe('updateLogistics()', () => {
    it('updates an existing logistics item by id', () => {
      const initialLogistics = [
        { id: 1, provider: 'DHL', cost: 10 },
        { id: 2, provider: 'FedEx', cost: 15 }
      ]
      useLogisticsStore.setState({ logistics: initialLogistics })

      useLogisticsStore.getState().updateLogistics(1, { cost: 12 })

      const state = useLogisticsStore.getState()
      expect(state.logistics.find(l => l.id === 1)).toEqual({ id: 1, provider: 'DHL', cost: 12 })
      expect(state.logistics.find(l => l.id === 2)).toEqual(initialLogistics[1])
      expect(state.logistics.length).toBe(2)
    })

    it('does not modify logistics if id does not exist', () => {
      const initialLogistics = [{ id: 1, provider: 'DHL', cost: 10 }]
      useLogisticsStore.setState({ logistics: initialLogistics })

      useLogisticsStore.getState().updateLogistics(99, { cost: 12 })

      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual(initialLogistics)
    })
  })

  describe('removeLogistics()', () => {
    it('removes a logistics item by id', () => {
      const initialLogistics = [
        { id: 1, provider: 'DHL' },
        { id: 2, provider: 'FedEx' },
        { id: 3, provider: 'UPS' }
      ]
      useLogisticsStore.setState({ logistics: initialLogistics })

      useLogisticsStore.getState().removeLogistics(2)

      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual([
        { id: 1, provider: 'DHL' },
        { id: 3, provider: 'UPS' }
      ])
      expect(state.logistics.length).toBe(2)
    })

    it('does nothing if id does not exist', () => {
      const initialLogistics = [{ id: 1, provider: 'DHL' }]
      useLogisticsStore.setState({ logistics: initialLogistics })

      useLogisticsStore.getState().removeLogistics(99)

      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual(initialLogistics)
    })

    it('handles empty logistics array', () => {
      useLogisticsStore.getState().removeLogistics(1)
      const state = useLogisticsStore.getState()
      expect(state.logistics).toEqual([])
    })
  })
})
