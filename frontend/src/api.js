import axios from 'axios'
import { getToken } from './contexts/AuthContext'

const api = axios.create({
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('stepik_session_token')
      if (!window.location.pathname.startsWith('/api/auth')) {
        window.location.reload()
      }
    }
    return Promise.reject(error)
  }
)

export default api
