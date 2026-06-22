<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.back()">‹</button>
      <h1>{{ deptName ? `${deptName} 병원` : '주변 병원' }}</h1>
    </header>

    <div class="page split-page">
      <!-- 좌측(데스크톱) / 상단(모바일): 위치 + 지도 -->
      <div class="map-col">
      <!-- 위치 기준 표시 + 변경 -->
      <div class="location-bar">
        <span class="location-label">
          📍 {{ locationStore.label || '위치 확인 중' }}
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

      <!-- 지도 -->
      <div class="map-holder" :class="{ picking: pickMode }">
        <KakaoMap
          v-if="locationStore.hasLocation"
          :center="{ lat: locationStore.lat, lng: locationStore.lng }"
          :hospitals="hospitals"
          :user-location="{ lat: locationStore.lat, lng: locationStore.lng }"
          height="100%"
          :highlight-top="3"
          @marker-click="onMarkerClick"
          @marker-detail="goDetail($event.id)"
          @map-click="onMapClick"
        />
      </div>
      </div>

      <!-- 우측(데스크톱) / 하단(모바일): 리스트 -->
      <div class="list-col">
      <p v-if="expanded && radiusKm" class="location-notice">
        🔭 주변에 결과가 없어 반경을 {{ radiusKm }}km까지 넓혀 찾았어요.
      </p>

      <!-- 리스트 -->
      <div v-if="loading" style="padding: 40px 0">
        <div class="spinner"></div>
        <p class="sub-text" style="text-align: center; margin-top: 12px">
          가까운 병원을 찾고 있어요...
        </p>
      </div>

      <template v-else>
        <div class="list-toolbar">
          <p class="count-text">
            거리순 추천 <strong>{{ hospitals.length }}곳</strong>
          </p>
          <button
            class="open-toggle"
            :class="{ active: openOnly }"
            @click="toggleOpenOnly"
          >
            🟢 영업중만 {{ openOnly ? 'ON' : 'OFF' }}
          </button>
        </div>
        <div class="hospital-list">
          <button
            v-for="h in hospitals"
            :key="h.id"
            class="hospital-card card"
            :class="{ active: h.id === activeId }"
            @click="goDetail(h.id)"
          >
            <div class="h-top">
              <span class="h-name">{{ h.name }}</span>
              <span class="h-dist" v-if="h.distance_km != null">{{ h.distance_km }}km</span>
            </div>
            <p class="h-addr">{{ h.address }}</p>
            <p class="h-rating" v-if="h.review_count">
              <span class="stars">★</span> {{ h.rating.toFixed(1) }}
              <span class="h-rating-count">({{ h.review_count }})</span>
            </p>
            <div class="h-tags">
              <span v-for="r in h.reasons" :key="r" class="tag" :class="r === '영업중' ? 'tag-green' : 'tag-blue'">
                {{ r }}
              </span>
              <span v-if="!h.is_open" class="tag tag-gray">영업종료</span>
              <span v-for="d in h.departments.slice(0, 3)" :key="d" class="tag tag-gray">{{ d }}</span>
            </div>
          </button>
        </div>

        <div v-if="hospitals.length === 0" class="card" style="text-align: center; padding: 28px">
          <p>😢 조건에 맞는 병원을 찾지 못했어요.</p>
          <button v-if="openOnly" class="btn btn-outline" style="margin-top: 14px" @click="toggleOpenOnly">
            영업 종료된 병원도 보기
          </button>
        </div>
      </template>

      <p class="disclaimer">진료시간·운영 여부는 변동될 수 있으니 방문 전 전화로 확인하세요.</p>
      </div><!-- /list-col -->
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { getDepartments, getHospitals } from '@/api/client'
import KakaoMap from '@/components/KakaoMap.vue'
import { LOCATION_PRESETS, useLocationStore } from '@/stores/location'
import { useRecommendStore } from '@/stores/recommend'

const router = useRouter()
const store = useRecommendStore()
const locationStore = useLocationStore()

const hospitals = ref([])
const loading = ref(true)
const radiusKm = ref(null)
const expanded = ref(false)
const activeId = ref(null)
const showPicker = ref(false)
const pickMode = ref(false)
const openOnly = ref(false) // '영업중만' 토글 (기본: 전체 보기)

const deptName = computed(() => store.selectedDepartment?.department ?? '')

let departmentId = null

async function resolveDepartmentId() {
  departmentId = store.selectedDepartment?.department_id
  if (!departmentId && store.selectedDepartment?.fallbackName) {
    try {
      const { data } = await getDepartments()
      departmentId = data.find((d) => d.name === store.selectedDepartment.fallbackName)?.id
    } catch { /* 무시 — 전체 병원으로 진행 */ }
  }
}

// GPS 갱신과 수동 변경이 겹칠 때 늦게 도착한 응답이 최신 결과를 덮지 않도록 요청 번호 관리
let requestSeq = 0

async function loadHospitals() {
  const seq = ++requestSeq
  loading.value = true
  try {
    const { data } = await getHospitals({
      lat: locationStore.lat,
      lng: locationStore.lng,
      departmentId,
      openOnly: openOnly.value,
    })
    if (seq !== requestSeq) return // 더 새로운 요청이 이미 나감
    hospitals.value = data.hospitals
    radiusKm.value = data.radius_km
    expanded.value = data.expanded
  } catch {
    if (seq === requestSeq) hospitals.value = []
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

onMounted(async () => {
  // 기본 좌표를 즉시 채워 지도·리스트를 바로 렌더, GPS는 백그라운드 갱신
  locationStore.ensureLocation()
  await resolveDepartmentId()
  loadHospitals()
})

// 위치가 바뀌면(GPS 도착·프리셋·지도 클릭) 병원 목록 갱신
watch(() => [locationStore.lat, locationStore.lng], () => {
  loadHospitals()
})

function toggleOpenOnly() {
  openOnly.value = !openOnly.value
  loadHospitals()
}

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

function onMarkerClick(h) {
  activeId.value = h.id
}

function goDetail(id) {
  router.push({ name: 'hospital-detail', params: { id } })
}
</script>

<style scoped>
.location-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.location-label {
  font-size: 13px;
  font-weight: 700;
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

/* 지도 컨테이너: 모바일 260px, 데스크톱은 화면 높이에 맞춰 크게 */
.map-holder {
  height: 260px;
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
    top: 76px; /* 헤더 높이만큼 */
  }
  .map-holder {
    height: calc(100vh - 210px);
    min-height: 420px;
  }
  .list-col {
    min-height: calc(100vh - 140px);
    display: flex;
    flex-direction: column;
  }
}
.location-notice {
  font-size: 13px;
  color: var(--text-sub);
  background: var(--primary-light);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.list-toolbar {
  margin: 16px 2px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.count-text {
  font-size: 14px;
  color: var(--text-sub);
}
.open-toggle {
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 7px 12px;
  cursor: pointer;
  white-space: nowrap;
}
.open-toggle.active {
  border-color: var(--success);
  color: var(--success);
  background: var(--success-light);
}
.hospital-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.hospital-card {
  text-align: left;
  cursor: pointer;
  font-family: inherit;
  transition: border-color 0.15s;
}
.hospital-card:hover,
.hospital-card.active {
  border-color: var(--primary);
}
.h-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.h-name {
  font-size: 16px;
  font-weight: 700;
}
.h-dist {
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  white-space: nowrap;
}
.h-addr {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-sub);
}
.h-rating {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 700;
}
.h-rating .stars {
  color: #f5a623;
}
.h-rating-count {
  color: var(--text-sub);
  font-weight: 400;
}
.h-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
