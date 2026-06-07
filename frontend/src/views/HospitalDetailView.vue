<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.back()">‹</button>
      <h1>병원 정보</h1>
    </header>

    <div class="page">
      <div v-if="loading" style="padding: 60px 0">
        <div class="spinner"></div>
      </div>

      <template v-else-if="hospital">
        <h2 class="section-title">{{ hospital.name }}</h2>
        <div class="dept-tags">
          <span v-for="d in hospital.departments" :key="d" class="tag tag-blue">{{ d }}</span>
        </div>

        <!-- 미니맵 (길찾기 시 경로 표시) -->
        <KakaoMap
          style="margin-top: 16px"
          :center="{ lat: hospital.latitude, lng: hospital.longitude }"
          :hospitals="[hospital]"
          :level="3"
          :height="route ? '260px' : '200px'"
          :show-detail-link="false"
          :user-location="route ? { lat: locationStore.lat, lng: locationStore.lng } : null"
          :path="route?.path ?? null"
        />

        <!-- 길찾기 결과 -->
        <div v-if="route" class="card route-card">
          🚗 <strong>{{ (route.distance_m / 1000).toFixed(1) }}km</strong> ·
          약 <strong>{{ Math.max(1, Math.round(route.duration_s / 60)) }}분</strong>
          <span class="route-from">({{ locationStore.label }} 기준 자동차)</span>
        </div>
        <p v-if="routeError" class="route-error">{{ routeError }}</p>

        <!-- 정보 -->
        <div class="card info-card">
          <div class="info-row">
            <span class="info-label">📍 주소</span>
            <span>{{ hospital.address }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">📞 전화</span>
            <span>{{ hospital.phone || '정보 없음' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">🕐 진료시간</span>
            <span>{{ hospital.open_time }} ~ {{ hospital.close_time }}</span>
          </div>
        </div>

        <!-- 액션 버튼 -->
        <div class="action-row">
          <button class="btn btn-outline" :disabled="routeLoading" @click="findRoute">
            {{ routeLoading ? '경로 찾는 중...' : '🧭 길찾기' }}
          </button>
          <a v-if="hospital.phone" class="btn btn-primary" :href="`tel:${hospital.phone}`">
            📞 전화하기
          </a>
        </div>
      </template>

      <div v-else class="card" style="text-align: center; padding: 28px">
        <p>병원 정보를 불러오지 못했어요.</p>
      </div>

      <p class="disclaimer">진료시간은 변동될 수 있으니 방문 전 전화로 확인하세요.</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getDirections, getHospitalDetail } from '@/api/client'
import KakaoMap from '@/components/KakaoMap.vue'
import { useLocationStore } from '@/stores/location'

const props = defineProps({ id: { type: String, required: true } })

const router = useRouter()
const locationStore = useLocationStore()
const hospital = ref(null)
const loading = ref(true)
const route = ref(null)
const routeLoading = ref(false)
const routeError = ref('')

onMounted(async () => {
  locationStore.ensureLocation()
  try {
    const { data } = await getHospitalDetail(props.id)
    hospital.value = data
  } catch {
    hospital.value = null
  } finally {
    loading.value = false
  }
})

async function findRoute() {
  routeLoading.value = true
  routeError.value = ''
  try {
    const { data } = await getDirections({
      originLat: locationStore.lat,
      originLng: locationStore.lng,
      destLat: hospital.value.latitude,
      destLng: hospital.value.longitude,
    })
    route.value = data
  } catch (err) {
    routeError.value = err.response?.data?.detail ?? '경로를 불러오지 못했어요.'
  } finally {
    routeLoading.value = false
  }
}
</script>

<style scoped>
.dept-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.info-card {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.info-row {
  display: flex;
  gap: 12px;
  font-size: 14px;
  line-height: 1.5;
}
.info-label {
  min-width: 86px;
  font-weight: 700;
  color: var(--text-sub);
  white-space: nowrap;
}
.action-row {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.route-card {
  margin-top: 12px;
  font-size: 14px;
  background: var(--primary-light);
  border-color: #cdd9f7;
}
.route-from {
  font-size: 12px;
  color: var(--text-sub);
  margin-left: 4px;
}
.route-error {
  margin-top: 10px;
  font-size: 13px;
  color: var(--danger);
}
</style>
