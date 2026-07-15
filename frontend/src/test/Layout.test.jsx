import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import TestRouter from './TestRouter'
import Layout from '../components/Layout'

describe('Layout', () => {
  it('renders children', () => {
    render(
      <TestRouter>
        <Layout>
          <div>Test Content</div>
        </Layout>
      </TestRouter>
    )
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('renders sidebar navigation', () => {
    render(
      <TestRouter>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>
    )
    expect(screen.getByText('Дашборд')).toBeInTheDocument()
    expect(screen.getByText('Курсы')).toBeInTheDocument()
    expect(screen.getByText('Финансы')).toBeInTheDocument()
    expect(screen.getByText('Когорты')).toBeInTheDocument()
  })

  it('renders logo', () => {
    render(
      <TestRouter>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>
    )
    expect(screen.getByText('STEPIK CONTROL')).toBeInTheDocument()
  })

  it('renders sync indicator', () => {
    render(
      <TestRouter>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>
    )
    expect(screen.getByText('SYNCED')).toBeInTheDocument()
  })

  it('renders version', () => {
    render(
      <TestRouter>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>
    )
    expect(screen.getByText('v0.1.0')).toBeInTheDocument()
  })

  it('renders read-only mode label', () => {
    render(
      <TestRouter>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>
    )
    expect(screen.getByText('Read-Only Mode')).toBeInTheDocument()
  })
})
