import axios from 'axios'
import { getToken } from './contexts/AuthContext'

const api = axios.create()

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
