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
        <div class="rating-summary" v-if="hospital.review_count">
          <span class="stars">{{ starText(Math.round(hospital.rating)) }}</span>
          <strong>{{ hospital.rating.toFixed(1) }}</strong>
          <span class="rating-count">후기 {{ hospital.review_count }}개</span>
        </div>
        <div class="rating-summary rating-empty" v-else>아직 후기가 없어요</div>
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

        <!-- 후기 -->
        <section class="reviews">
          <h3 class="reviews-title">후기 <span>{{ reviews.length }}</span></h3>

          <!-- 작성 폼 (로그인 시) -->
          <form v-if="auth.isLoggedIn" class="card review-form" @submit.prevent="submitReview">
            <p class="form-label">{{ myReview ? '내 후기 수정' : '후기 남기기' }}</p>
            <div class="star-input">
              <button
                v-for="n in 5"
                :key="n"
                type="button"
                class="star-btn"
                :class="{ on: n <= form.rating }"
                @click="form.rating = n"
              >★</button>
            </div>
            <textarea
              v-model="form.content"
              class="review-textarea"
              rows="3"
              maxlength="1000"
              placeholder="진료·대기시간·친절도 등 방문 경험을 공유해 주세요. (선택)"
            ></textarea>
            <p v-if="reviewError" class="route-error">{{ reviewError }}</p>
            <button class="btn btn-primary" :disabled="submitting" type="submit">
              {{ submitting ? '저장 중...' : myReview ? '수정하기' : '등록하기' }}
            </button>
          </form>
          <div v-else class="card login-hint">
            후기를 남기려면 <RouterLink to="/login">로그인</RouterLink>이 필요해요.
          </div>

          <!-- 목록 -->
          <p v-if="!reviews.length" class="empty-reviews">첫 후기를 남겨보세요!</p>
          <ul v-else class="review-list">
            <li v-for="r in reviews" :key="r.id" class="card review-item">
              <div class="review-head">
                <span class="stars">{{ starText(r.rating) }}</span>
                <span class="review-nick">{{ r.nickname || '익명' }}</span>
                <span v-if="r.department_name" class="tag tag-blue">{{ r.department_name }}</span>
                <button v-if="r.is_mine" class="review-del" @click="removeReview(r.id)">삭제</button>
              </div>
              <p v-if="r.content" class="review-content">{{ r.content }}</p>
              <span class="review-date">{{ r.created_at?.slice(0, 10) }}</span>
            </li>
          </ul>
        </section>
      </template>

      <div v-else class="card" style="text-align: center; padding: 28px">
        <p>병원 정보를 불러오지 못했어요.</p>
      </div>

      <p class="disclaimer">진료시간은 변동될 수 있으니 방문 전 전화로 확인하세요.</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  deleteHospitalReview,
  getDirections,
  getHospitalDetail,
  getHospitalReviews,
  postHospitalReview,
} from '@/api/client'
import KakaoMap from '@/components/KakaoMap.vue'
import { useAuthStore } from '@/stores/auth'
import { useLocationStore } from '@/stores/location'

const props = defineProps({ id: { type: String, required: true } })

const router = useRouter()
const locationStore = useLocationStore()
const auth = useAuthStore()
const hospital = ref(null)
const loading = ref(true)
const route = ref(null)
const routeLoading = ref(false)
const routeError = ref('')

const reviews = ref([])
const myReview = ref(null) // 내가 이미 남긴 후기 (있으면 수정 모드)
const form = reactive({ rating: 5, content: '' })
const submitting = ref(false)
const reviewError = ref('')

const starText = (n) => '★'.repeat(n) + '☆'.repeat(5 - n)

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
  loadReviews()
})

async function loadReviews() {
  try {
    const { data } = await getHospitalReviews(props.id)
    reviews.value = data
    myReview.value = data.find((r) => r.is_mine) ?? null
    if (myReview.value) {
      form.rating = myReview.value.rating
      form.content = myReview.value.content
    }
  } catch {
    reviews.value = []
  }
}

async function submitReview() {
  submitting.value = true
  reviewError.value = ''
  try {
    await postHospitalReview(props.id, { rating: form.rating, content: form.content })
    await loadReviews()
    await refreshRating()
  } catch (err) {
    reviewError.value = err.response?.data?.detail ?? '후기 저장에 실패했어요.'
  } finally {
    submitting.value = false
  }
}

async function removeReview(reviewId) {
  if (!confirm('후기를 삭제할까요?')) return
  try {
    await deleteHospitalReview(reviewId)
    myReview.value = null
    form.rating = 5
    form.content = ''
    await loadReviews()
    await refreshRating()
  } catch (err) {
    reviewError.value = err.response?.data?.detail ?? '삭제에 실패했어요.'
  }
}

// 평점 요약(평균·개수)을 다시 받아 헤더 갱신
async function refreshRating() {
  try {
    const { data } = await getHospitalDetail(props.id)
    if (hospital.value) {
      hospital.value.rating = data.rating
      hospital.value.review_count = data.review_count
    }
  } catch { /* 무시 */ }
}

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

/* ── 평점·후기 ── */
.rating-summary {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
}
.rating-summary .stars {
  color: #f5a623;
  letter-spacing: 1px;
}
.rating-count {
  font-size: 13px;
  color: var(--text-sub);
}
.rating-empty {
  font-size: 13px;
  color: var(--text-sub);
}
.reviews {
  margin-top: 28px;
}
.reviews-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
}
.reviews-title span {
  color: var(--primary);
}
.review-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.form-label {
  font-weight: 700;
  font-size: 14px;
}
.star-input {
  display: flex;
  gap: 2px;
}
.star-btn {
  background: none;
  border: none;
  font-size: 26px;
  line-height: 1;
  color: #d9d9d9;
  cursor: pointer;
  padding: 0;
}
.star-btn.on {
  color: #f5a623;
}
.review-textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--border, #e0e0e0);
  border-radius: 8px;
  padding: 10px;
  font: inherit;
  box-sizing: border-box;
}
.login-hint {
  font-size: 14px;
  text-align: center;
  padding: 16px;
  color: var(--text-sub);
  margin-bottom: 16px;
}
.empty-reviews {
  font-size: 14px;
  color: var(--text-sub);
  text-align: center;
  padding: 20px 0;
}
.review-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.review-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.review-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.review-head .stars {
  color: #f5a623;
  font-size: 14px;
}
.review-nick {
  font-weight: 700;
  font-size: 14px;
}
.review-del {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--danger);
  font-size: 12px;
  cursor: pointer;
}
.review-content {
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.review-date {
  font-size: 12px;
  color: var(--text-sub);
}
</style>
