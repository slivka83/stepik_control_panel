const store = {}

export function getCached(key) {
  return store[key] ?? null
}

export function setCached(key, value) {
  store[key] = value
}

export function clearCache() {
  Object.keys(store).forEach(k => delete store[k])
}
