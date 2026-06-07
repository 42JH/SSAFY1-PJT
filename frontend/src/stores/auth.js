import { defineStore } from 'pinia'

import { client } from '@/api/client'

/** JWT 인증 상태. 토큰은 localStorage에 보관 (데모 수준). */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    access: localStorage.getItem('itdoc_access') || null,
    refresh: localStorage.getItem('itdoc_refresh') || null,
    user: JSON.parse(localStorage.getItem('itdoc_user') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.access,
  },
  actions: {
    setSession({ access, refresh, user }) {
      this.access = access
      this.refresh = refresh
      this.user = user
      localStorage.setItem('itdoc_access', access)
      localStorage.setItem('itdoc_refresh', refresh)
      localStorage.setItem('itdoc_user', JSON.stringify(user))
    },
    async signup(email, password, nickname) {
      const { data } = await client.post('/auth/signup/', { email, password, nickname })
      this.setSession(data)
    },
    async login(email, password) {
      const { data } = await client.post('/auth/login/', { email, password })
      this.setSession(data)
    },
    logout() {
      this.access = null
      this.refresh = null
      this.user = null
      localStorage.removeItem('itdoc_access')
      localStorage.removeItem('itdoc_refresh')
      localStorage.removeItem('itdoc_user')
    },
  },
})
