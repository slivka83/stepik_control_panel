import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

describe('App', () => {
  it('renders without crashing', () => {
    const App = require('../App').default
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })

  it('renders router wrapper', () => {
    const App = require('../App').default
    const { container } = render(<App />)
    expect(container.querySelector('div')).not.toBeNull()
  })
})
