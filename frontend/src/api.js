import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  withCredentials: true,
})

let isRefreshing = false
let refreshPromise = null

async function refreshSession() {
  if (!isRefreshing) {
    isRefreshing = true
    refreshPromise = fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    }).finally(() => {
      isRefreshing = false
    })
  }
  const res = await refreshPromise
  return res.ok
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const refreshed = await refreshSession()
      if (refreshed) {
        return api(originalRequest)
      }
      window.location.href = '/'
    }
    return Promise.reject(error)
  },
)

export default api
