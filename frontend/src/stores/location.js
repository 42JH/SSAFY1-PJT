import { defineStore } from 'pinia'

// 위치 권한 거부/실패 시 폴백 좌표: 구미시청 인근
export const DEFAULT_LOCATION = { lat: 36.1195, lng: 128.3446, label: '구미시청' }

// 데스크톱(IP 기반)에서 위치가 엉뚱하게 잡힐 때 쓰는 주요 지점 프리셋
export const LOCATION_PRESETS = [
  { lat: 36.1195, lng: 128.3446, label: '구미시청' },
  { lat: 36.1281, lng: 128.3312, label: '구미역' },
  { lat: 36.1042, lng: 128.4201, label: '인동' },
  { lat: 36.1452, lng: 128.4102, label: '옥계' },
  { lat: 36.1398, lng: 128.1136, label: '김천' },
  { lat: 35.9946, lng: 128.3967, label: '왜관' },
]

/** Geolocation 좌표 수집 및 상태 관리.
 *  source: 'gps'(브라우저 위치) | 'default'(폴백) | 'manual'(직접 설정)
 */
export const useLocationStore = defineStore('location', {
  state: () => ({
    lat: null,
    lng: null,
    source: null,
    label: '',
    loading: false,
  }),
  getters: {
    hasLocation: (s) => s.lat != null && s.lng != null,
    usingDefault: (s) => s.source === 'default',
  },
  actions: {
    /** 지도를 즉시 띄울 수 있게 기본 좌표를 동기로 채우고, GPS는 백그라운드로 갱신.
     *  GPS를 기다리지 않으므로 지도 렌더가 위치 응답에 블로킹되지 않는다. */
    ensureLocation() {
      if (!this.hasLocation) {
        this.lat = DEFAULT_LOCATION.lat
        this.lng = DEFAULT_LOCATION.lng
        this.source = 'default'
        this.label = DEFAULT_LOCATION.label
      }
      // 수동 설정이 아니면 GPS 갱신 시도 (await 하지 않음)
      // requireAccurate: IP 기반 추정(대구 등 엉뚱한 도시)이 기본 위치를 덮지 않도록
      if (this.source !== 'manual') this.fetchLocation({ force: true, requireAccurate: true })
    },
    async fetchLocation({ force = false, requireAccurate = false } = {}) {
      if (this.hasLocation && !force) return
      this.loading = true
      try {
        const pos = await new Promise((resolve, reject) => {
          if (!navigator.geolocation) {
            reject(new Error('geolocation unsupported'))
            return
          }
          // 데스크톱은 IP/와이파이 기반이라 highAccuracy 의미가 없고 느려지기만 함
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: false,
            timeout: 5000,
            maximumAge: 60000,
          })
        })
        // 사용자가 그 사이 수동 설정했으면 GPS로 덮어쓰지 않음
        if (this.source !== 'manual') {
          const { latitude: lat, longitude: lng } = pos.coords
          const accuracy = pos.coords.accuracy ?? 99999
          const accurate = accuracy <= 3000
          // 구미·김천·칠곡 권역 bbox — 부정확해도 권역 안이면 쓸 만한 신호
          const inRegion = lat >= 35.85 && lat <= 36.45 && lng >= 127.95 && lng <= 128.65
          // 자동 갱신: 정확하거나(폰 GPS) 권역 안(IP라도 구미 인근)일 때만 적용.
          // 대구 등 권역 밖 IP 추정은 무시 — 구미시청 기본값이 더 합리적
          if (requireAccurate && !accurate && !inRegion) return
          this.lat = lat
          this.lng = lng
          this.source = 'gps'
          this.label = accurate ? '내 위치' : '대략적 위치 (±' + Math.round(accuracy / 1000) + 'km)'
        }
      } catch {
        // 권한 거부·실패 시: 기존 좌표(기본/수동) 유지, 없으면 기본 좌표
        if (!this.hasLocation) {
          this.lat = DEFAULT_LOCATION.lat
          this.lng = DEFAULT_LOCATION.lng
          this.source = 'default'
          this.label = DEFAULT_LOCATION.label
        }
      } finally {
        this.loading = false
      }
    },
    setManualLocation(lat, lng, label = '직접 설정') {
      this.lat = lat
      this.lng = lng
      this.source = 'manual'
      this.label = label
    },
  },
})
