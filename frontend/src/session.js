// Whether the browser currently has an authenticated panel session.
// Kept outside api.js so tests that mock the axios instance don't break auth.
let hasSession = false;

export function setHasSession(value) {
  hasSession = Boolean(value);
}

export function getHasSession() {
  return hasSession;
}
