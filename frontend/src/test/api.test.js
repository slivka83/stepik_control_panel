import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockCreate = vi.hoisted(() =>
  vi.fn(() => ({
    get: vi.fn(),
    interceptors: { response: { use: vi.fn() } },
    defaults: {},
  })),
);

vi.mock('axios', () => ({
  default: { create: mockCreate },
}));

describe('api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exports default axios instance', async () => {
    const mod = await import('../api');
    expect(mod.default).toBeDefined();
  });
});
