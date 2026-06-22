<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.back()">‹</button>
      <h1>가까운 응급실</h1>
    </header>

    <div class="page split-page">
      <!-- 좌측(데스크톱)/상단(모바일): 119 + 지도 -->
      <div class="map-col">
        <a class="call-119" href="tel:119">
          🚨 생명이 위급하면 먼저 <strong>119</strong> · 전화하기
        </a>

        <!-- 위치 기준 표시 + 변경 -->
        <div class="location-bar">
          <span class="location-label">
            📍 {{ locationStore.label || '위치 확인 중' }} 기준 거리순
            <small v-if="locationStore.usingDefault">(위치 권한 없음 — 기본 위치)</small>
          </span>
          <button class="location-change-btn" @click="showPicker = !showPicker">
            {{ showPicker ? '닫기' : '위치 변경' }}
          </button>
        </div>

        <!-- 위치 선택 패널 -->
        <div v-if="showPicker" class="card picker-panel">
          <p class="picker-title">주요 지점에서 선택</p>
          <div class="preset-chips">
            <button
              v-for="p in LOCATION_PRESETS"
              :key="p.label"
              class="preset-chip"
              :class="{ active: locationStore.label === p.label }"
              @click="usePreset(p)"
            >
              {{ p.label }}
            </button>
          </div>
          <div class="picker-actions">
            <button class="picker-action" @click="retryGps">🛰️ 현재 위치 다시 찾기</button>
            <button class="picker-action" :class="{ active: pickMode }" @click="pickMode = !pickMode">
              {{ pickMode ? '🗺️ 지도를 클릭하세요...' : '🗺️ 지도에서 직접 선택' }}
            </button>
          </div>
        </div>

        <div class="map-holder" :class="{ picking: pickMode }">
          <KakaoMap
            v-if="locationStore.hasLocation"
            :center="{ lat: locationStore.lat, lng: locationStore.lng }"
            :hospitals="mapMarkers"
            :user-location="{ lat: locationStore.lat, lng: locationStore.lng }"
            :show-detail-link="false"
            :highlight-top="3"
            :path="route?.path ?? null"
            height="100%"
            @map-click="onMapClick"
          />
        </div>
      </div>

      <!-- 우측(데스크톱)/하단(모바일): 응급의료기관 리스트 -->
      <div class="list-col">
        <div v-if="loading" style="padding: 40px 0; text-align: center">
          <div class="spinner"></div>
        </div>

        <div v-else-if="!centers.length" class="card empty-card">
          <p><strong>주변 응급의료기관 정보가 없어요.</strong></p>
          <p class="sub-text">
            아직 데이터가 적재되지 않았거나 권역 밖일 수 있어요.<br />
            급하면 119, 또는 공식 응급의료포털에서 확인하세요.
          </p>
          <a
            class="btn btn-outline-danger"
            href="https://www.e-gen.or.kr/egen/emergency_room_search.do"
            target="_blank"
            rel="noopener"
          >
            🏥 응급의료포털(E-Gen) 열기
          </a>
        </div>

        <template v-else>
          <p class="list-caption">응급실 보유 기관 {{ centers.length }}곳 · 가까운 순</p>
          <ul class="er-list">
            <li v-for="(c, idx) in centers" :key="c.id" class="card er-item">
              <div class="er-rank" :class="`rank-${Math.min(idx + 1, 4)}`">{{ idx + 1 }}</div>
              <div class="er-body">
                <div class="er-top">
                  <strong class="er-name">{{ c.name }}</strong>
                  <span v-if="c.type" class="er-type">{{ c.type }}</span>
                </div>
                <p class="er-addr">{{ c.address }}</p>
                <div class="er-meta">
                  <span class="er-dist">📍 {{ c.distance_km }}km</span>
                  <span v-if="route && routeCenterId === c.id" class="er-route">
                    🚗 {{ (route.distance_m / 1000).toFixed(1) }}km · 약
                    {{ Math.max(1, Math.round(route.duration_s / 60)) }}분
                  </span>
                </div>
                <div class="er-actions">
                  <button
                    class="btn btn-outline btn-sm"
                    :disabled="routeLoadingId === c.id"
                    @click="findRoute(c)"
                  >
                    {{ routeLoadingId === c.id ? '경로 찾는 중...' : '🧭 길찾기' }}
                  </button>
                  <a
                    v-if="c.er_phone || c.phone"
                    class="btn btn-danger btn-sm"
                    :href="`tel:${telDigits(c.er_phone || c.phone)}`"
                  >
                    📞 응급실 {{ c.er_phone || c.phone }}
                  </a>
                </div>
                <p v-if="routeError && routeErrorId === c.id" class="er-route-error">
                  {{ routeError }}
                </p>
              </div>
            </li>
          </ul>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getDirections, getEmergencyCenters } from '@/api/client'
import KakaoMap from '@/components/KakaoMap.vue'
import { LOCATION_PRESETS, useLocationStore } from '@/stores/location'

const router = useRouter()
const locationStore = useLocationStore()

const centers = ref([])
const loading = ref(true)

// 위치 변경 패널
const showPicker = ref(false)
const pickMode = ref(false)

// 길찾기(인라인): 선택한 기관 한 곳의 경로를 지도에 표시
const route = ref(null)
const routeCenterId = ref(null)
const routeLoadingId = ref(null)
const routeError = ref('')
const routeErrorId = ref(null)

// KakaoMap은 병원 배열 형태를 받으므로 맞춰 변환
const mapMarkers = computed(() =>
  centers.value.map((c) => ({
    id: c.id,
    name: c.name,
    latitude: c.latitude,
    longitude: c.longitude,
    distance_km: c.distance_km,
  })),
)

function telDigits(tel) {
  return String(tel).replace(/[^0-9]/g, '')
}

// 늦게 도착한 위치 갱신이 최신 결과를 덮지 않도록 요청 번호 관리
let seq = 0
async function load() {
  const my = ++seq
  loading.value = true
  // 위치가 바뀌면 이전 경로는 더 이상 유효하지 않으므로 지움
  clearRoute()
  try {
    const { data } = await getEmergencyCenters({
      lat: locationStore.lat,
      lng: locationStore.lng,
    })
    if (my !== seq) return
    centers.value = data.centers ?? []
  } catch {
    if (my === seq) centers.value = []
  } finally {
    if (my === seq) loading.value = false
  }
}

onMounted(() => {
  // 기본 좌표 즉시 채움 → 바로 조회, GPS는 백그라운드 갱신
  locationStore.ensureLocation()
  if (locationStore.hasLocation) load()
})

// 위치가 바뀌면(GPS 도착 등) 다시 조회
watch(
  () => [locationStore.lat, locationStore.lng],
  () => {
    if (locationStore.hasLocation) load()
  },
)

// --- 위치 변경 ---
function usePreset(p) {
  locationStore.setManualLocation(p.lat, p.lng, p.label)
  showPicker.value = false
  pickMode.value = false
}

async function retryGps() {
  await locationStore.fetchLocation({ force: true })
  showPicker.value = false
}

function onMapClick({ lat, lng }) {
  if (!pickMode.value) return
  locationStore.setManualLocation(lat, lng, '지도에서 선택')
  pickMode.value = false
  showPicker.value = false
}

// --- 길찾기 ---
function clearRoute() {
  route.value = null
  routeCenterId.value = null
  routeError.value = ''
  routeErrorId.value = null
}

async function findRoute(c) {
  // 같은 기관 길찾기를 다시 누르면 경로 숨김(토글)
  if (routeCenterId.value === c.id) {
    clearRoute()
    return
  }
  routeLoadingId.value = c.id
  routeError.value = ''
  routeErrorId.value = null
  try {
    const { data } = await getDirections({
      originLat: locationStore.lat,
      originLng: locationStore.lng,
      destLat: c.latitude,
      destLng: c.longitude,
    })
    route.value = data
    routeCenterId.value = c.id
  } catch (err) {
    route.value = null
    routeCenterId.value = null
    routeError.value = err.response?.data?.detail ?? '경로를 불러오지 못했어요.'
    routeErrorId.value = c.id
  } finally {
    routeLoadingId.value = null
  }
}
</script>

<style scoped>
.call-119 {
  display: block;
  text-align: center;
  background: #e5484d;
  color: #fff;
  font-weight: 700;
  padding: 12px;
  border-radius: var(--radius);
  margin-bottom: 12px;
  text-decoration: none;
}
.call-119 strong {
  font-size: 1.1em;
}
.location-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.location-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-muted, #6b7385);
}
.location-label small {
  color: var(--text-sub);
  font-weight: 400;
}
.location-change-btn {
  border: 1px solid var(--primary);
  background: var(--card);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 7px 12px;
  cursor: pointer;
  white-space: nowrap;
}
.picker-panel {
  margin-bottom: 12px;
  padding: 14px;
}
.picker-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-sub);
  margin-bottom: 8px;
}
.preset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preset-chip {
  padding: 8px 13px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card);
  font-size: 13px;
  cursor: pointer;
  color: var(--text);
}
.preset-chip.active,
.preset-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}
.picker-actions {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.picker-action {
  padding: 10px 8px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  color: var(--text);
}
.picker-action.active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}
.picking {
  outline: 2px dashed var(--primary);
  outline-offset: 2px;
  border-radius: var(--radius);
}
.map-holder {
  height: 260px;
}
.list-caption {
  font-size: 13px;
  color: var(--text-muted, #6b7385);
  margin: 4px 0 10px;
}
.er-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.er-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px;
}
.er-rank {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #c9762b;
  color: #fff;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.er-rank.rank-1 {
  background: #f5b301;
}
.er-rank.rank-2 {
  background: #9aa5b1;
}
.er-rank.rank-3 {
  background: #c9762b;
}
.er-rank.rank-4 {
  background: #b0b7c3;
}
.er-body {
  flex: 1 1 auto;
  min-width: 0;
}
.er-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.er-name {
  font-size: 15px;
}
.er-type {
  font-size: 11px;
  font-weight: 700;
  color: #2f6bff;
  background: #eaf1ff;
  border-radius: 999px;
  padding: 2px 8px;
}
.er-addr {
  font-size: 13px;
  color: var(--text-muted, #6b7385);
  margin: 4px 0;
}
.er-meta {
  font-size: 13px;
  font-weight: 600;
}
.er-dist {
  color: #18a35a;
}
.er-route {
  margin-left: 10px;
  color: #2f6bff;
}
.er-actions {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.er-route-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--danger, #e5484d);
}
.btn-sm {
  padding: 7px 12px;
  font-size: 13px;
}
.empty-card {
  text-align: center;
  padding: 28px 18px;
}
.empty-card .btn {
  margin-top: 12px;
}

/* 데스크톱 분할 뷰 (지도 좌측 고정 + 리스트 우측 스크롤) */
@media (min-width: 1024px) {
  .split-page {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(320px, 1fr);
    gap: 20px;
    align-items: start;
  }
  .map-col {
    position: sticky;
    top: 76px;
  }
  .map-holder {
    height: calc(100vh - 240px);
    min-height: 420px;
  }
}
</style>
