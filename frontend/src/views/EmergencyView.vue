<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.push({ name: 'home' })">‹</button>
      <h1>응급 안내</h1>
    </header>

    <div class="page emergency-page">
      <div class="alert-circle">🚨</div>

      <h2 class="alert-title">지금은 응급 상황일 수<br />있어요</h2>
      <p class="sub-text" style="text-align: center; margin-top: 10px">
        입력하신 증상에서 응급 신호가 감지되었어요.<br />
        진료과 추천보다, <strong>즉시 도움을 요청하세요.</strong>
      </p>

      <!-- 감지된 응급 키워드 (추천 근거) -->
      <div v-if="store.emergencyKeywords.length" class="card keyword-card">
        <p class="keyword-title">감지된 응급 신호</p>
        <div class="keyword-tags">
          <span v-for="k in store.emergencyKeywords" :key="k.keyword" class="tag tag-red">
            {{ k.keyword }}<template v-if="k.category"> · {{ k.category }}</template>
          </span>
        </div>
      </div>

      <div class="card tip-card">
        <p>💡 119 연결 시 <strong>위치·증상·의식 여부</strong>를 알려주시면 더 빨리 도울 수 있어요.</p>
      </div>

      <div class="action-col">
        <a class="btn btn-danger" href="tel:119">📞 119 전화하기</a>
        <button class="btn btn-outline-danger" @click="goEmergencyRooms">
          🏥 가까운 응급실 찾기
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

import { useRecommendStore } from '@/stores/recommend'

const router = useRouter()
const store = useRecommendStore()

function goEmergencyRooms() {
  // 일반 병·의원 전체가 아니라 응급실 보유 기관만 거리순으로 안내
  router.push({ name: 'emergency-rooms' })
}
</script>

<style scoped>
.emergency-page {
  align-items: center;
}
.alert-circle {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: var(--danger-light);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 38px;
  margin: 24px auto 18px;
}
.alert-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--danger);
  text-align: center;
  line-height: 1.4;
}
.keyword-card {
  margin-top: 22px;
  width: 100%;
}
.keyword-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-sub);
  margin-bottom: 10px;
}
.keyword-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tip-card {
  margin-top: 12px;
  width: 100%;
  font-size: 13px;
  line-height: 1.6;
  background: #fffaf0;
  border-color: #f3e3bd;
}
.action-col {
  margin-top: auto;
  padding-top: 24px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
