import axios from 'axios';
import { API_BASE, apiUrl } from './config';
import { getHasSession, setHasSession } from './session';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  withCredentials: true,
});

let isRefreshing = false;
let refreshPromise = null;

async function refreshSession() {
  if (!isRefreshing) {
    isRefreshing = true;
    refreshPromise = fetch(apiUrl('/auth/refresh'), {
      method: 'POST',
      credentials: 'include',
    })
      .then((res) => res.ok)
      // A network error must not turn the original 401 into a refresh crash.
      .catch(() => false)
      .finally(() => {
        isRefreshing = false;
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Пока сессии нет (страница открыта до входа), 401 — нормальный ответ,
      // а не «сессия истекла»: не уводим пользователя на дашборд.
      if (!getHasSession()) return Promise.reject(error);
      originalRequest._retry = true;
      const refreshed = await refreshSession();
      if (refreshed) {
        return api(originalRequest);
      }
      setHasSession(false);
      window.location.href = '/';
    }
    return Promise.reject(error);
  },
);

export default api;
