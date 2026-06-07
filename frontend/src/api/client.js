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
