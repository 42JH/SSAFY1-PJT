import axios from 'axios'

export const client = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 로그인 상태면 모든 요청에 JWT 부착 (게스트는 그대로 동작)
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('itdoc_access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

function clearTokens() {
  localStorage.removeItem('itdoc_access')
  localStorage.removeItem('itdoc_refresh')
  localStorage.removeItem('itdoc_user')
}

// 동시에 여러 요청이 401을 받아도 refresh는 한 번만 (요청 폭주 방지)
let refreshPromise = null

// 401 처리: access 토큰 만료 시 refresh로 자동 갱신 후 원요청 재시도.
// refresh도 만료됐으면 토큰을 비우고 인증 없이 한 번 더 시도 →
// 공개 엔드포인트(진료과·병원 등)가 게스트로 정상 동작하도록 보장.
client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { response, config } = error
    if (response?.status === 401 && config && !config._retried) {
      config._retried = true
      const refresh = localStorage.getItem('itdoc_refresh')
      if (refresh) {
        try {
          // 인터셉터 재진입 루프를 피하려고 순수 axios 사용
          if (!refreshPromise) {
            refreshPromise = axios
              .post('/api/auth/refresh/', { refresh })
              .finally(() => { refreshPromise = null })
          }
          const { data } = await refreshPromise
          localStorage.setItem('itdoc_access', data.access)
          if (data.refresh) localStorage.setItem('itdoc_refresh', data.refresh)
          config.headers.Authorization = `Bearer ${data.access}`
          return client(config)
        } catch {
          clearTokens() // refresh도 만료 → 게스트로 강등
        }
      } else {
        clearTokens()
      }
      delete config.headers.Authorization // 죽은 토큰 제거 후 게스트로 재시도
      return client(config)
    }
    return Promise.reject(error)
  },
)

/** 증상 텍스트 → 진료과 추천 (응급 분기 포함) */
export function postRecommend(symptomText) {
  return client.post('/recommend/', { symptom_text: symptomText })
}

/** 진료과 목록 */
export function getDepartments() {
  return client.get('/departments/')
}

/** 위치·진료과 기반 병원 추천 */
export function getHospitals({ lat, lng, departmentId, radius, openOnly } = {}) {
  const params = {}
  if (lat != null && lng != null) {
    params.lat = lat
    params.lng = lng
  }
  if (departmentId) params.department_id = departmentId
  if (radius) params.radius = radius
  if (openOnly) params.open_only = 1
  return client.get('/hospitals/', { params })
}

/** 병원 상세 */
export function getHospitalDetail(id) {
  return client.get(`/hospitals/${id}/`)
}

/** 자동차 길찾기 (카카오모빌리티 — 백엔드 프록시) */
export function getDirections({ originLat, originLng, destLat, destLng }) {
  return client.get('/directions/', {
    params: {
      origin_lat: originLat,
      origin_lng: originLng,
      dest_lat: destLat,
      dest_lng: destLng,
    },
  })
}
