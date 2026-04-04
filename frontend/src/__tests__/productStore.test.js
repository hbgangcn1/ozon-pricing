import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useProductStore } from '../stores/productStore'

describe('productStore.js', () => {
  const initialState = useProductStore.getState()
  
  beforeEach(() => {
    useProductStore.setState(initialState, true)
    vi.clearAllMocks()
  })

  describe('Initial state', () => {
    it('has correct initial state', () => {
      const state = useProductStore.getState()
      expect(state.products).toEqual([])
      expect(state.loading).toBe(false)
      expect(state.error).toBeNull()
    })
  })

  describe('setProducts()', () => {
    it('sets the products array', () => {
      const mockProducts = [{ id: 1, name: 'Product A' }, { id: 2, name: 'Product B' }]
      useProductStore.getState().setProducts(mockProducts)
      
      const state = useProductStore.getState()
      expect(state.products).toEqual(mockProducts)
    })
  })

  describe('setLoading()', () => {
    it('updates loading state', () => {
      useProductStore.getState().setLoading(true)
      expect(useProductStore.getState().loading).toBe(true)

      useProductStore.getState().setLoading(false)
      expect(useProductStore.getState().loading).toBe(false)
    })
  })

  describe('setError()', () => {
    it('updates error state', () => {
      const errorMsg = 'Failed to load products'
      useProductStore.getState().setError(errorMsg)
      expect(useProductStore.getState().error).toBe(errorMsg)

      useProductStore.getState().setError(null)
      expect(useProductStore.getState().error).toBeNull()
    })
  })

  describe('addProduct()', () => {
    it('appends a new product to the existing products array', () => {
      const initialProducts = [{ id: 1, name: 'Product A' }]
      useProductStore.setState({ products: initialProducts })

      const newProduct = { id: 2, name: 'Product B' }
      useProductStore.getState().addProduct(newProduct)

      const state = useProductStore.getState()
      expect(state.products).toEqual([...initialProducts, newProduct])
    })

    it('works when products array is empty', () => {
      const newProduct = { id: 1, name: 'Product A' }
      useProductStore.getState().addProduct(newProduct)

      const state = useProductStore.getState()
      expect(state.products).toEqual([newProduct])
    })
  })

  describe('updateProduct()', () => {
    it('updates an existing product by id', () => {
      const initialProducts = [
        { id: 1, name: 'Product A', price: 100 },
        { id: 2, name: 'Product B', price: 200 }
      ]
      useProductStore.setState({ products: initialProducts })

      useProductStore.getState().updateProduct(1, { price: 150 })

      const state = useProductStore.getState()
      expect(state.products.find(p => p.id === 1)).toEqual({ id: 1, name: 'Product A', price: 150 })
      expect(state.products.find(p => p.id === 2)).toEqual(initialProducts[1])
      expect(state.products.length).toBe(2)
    })

    it('does not modify products if id does not exist', () => {
      const initialProducts = [{ id: 1, name: 'Product A', price: 100 }]
      useProductStore.setState({ products: initialProducts })

      useProductStore.getState().updateProduct(99, { price: 150 })

      const state = useProductStore.getState()
      expect(state.products).toEqual(initialProducts)
    })
  })

  describe('removeProduct()', () => {
    it('removes a product by id', () => {
      const initialProducts = [
        { id: 1, name: 'Product A' },
        { id: 2, name: 'Product B' },
        { id: 3, name: 'Product C' }
      ]
      useProductStore.setState({ products: initialProducts })

      useProductStore.getState().removeProduct(2)

      const state = useProductStore.getState()
      expect(state.products).toEqual([
        { id: 1, name: 'Product A' },
        { id: 3, name: 'Product C' }
      ])
      expect(state.products.length).toBe(2)
    })

    it('does nothing if id does not exist', () => {
      const initialProducts = [{ id: 1, name: 'Product A' }]
      useProductStore.setState({ products: initialProducts })

      useProductStore.getState().removeProduct(99)

      const state = useProductStore.getState()
      expect(state.products).toEqual(initialProducts)
    })

    it('handles empty products array', () => {
      useProductStore.getState().removeProduct(1)
      const state = useProductStore.getState()
      expect(state.products).toEqual([])
    })
  })
})
