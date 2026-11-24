import '@testing-library/jest-dom';
import { vi } from 'vitest';

// AuthProvider calls /auth/me on mount. Tests that don't exercise auth should
// not wait for the real network (or 15s of retries): default to "not logged in".
if (!globalThis.fetch || !vi.isMockFunction(globalThis.fetch)) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: false,
    status: 401,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve({}),
  });
}

class ResizeObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {
    this.callback([{ contentRect: { width: 800, height: 400 } }]);
  }
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserver;

class IntersectionObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {
    this.callback([{ isIntersecting: true }]);
  }
  unobserve() {}
  disconnect() {}
}
globalThis.IntersectionObserver = IntersectionObserver;

globalThis.scrollTo = () => {};

Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
  value: () => ({ width: 800, height: 400, top: 0, left: 0, right: 800, bottom: 400 }),
});

Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
  configurable: true,
  get: () => 400,
});

Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
  configurable: true,
  get: () => 20,
});
