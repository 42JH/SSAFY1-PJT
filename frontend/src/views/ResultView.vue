<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.push({ name: 'symptom' })">‹</button>
      <h1>추천 결과</h1>
    </header>

    <div class="page">
      <!-- 입력 증상 요약 -->
      <div v-if="store.symptomText" class="symptom-summary card">
        <span class="tag tag-gray">입력 증상</span>
        <p>{{ store.symptomText }}</p>
      </div>

      <!-- 폴백: 매칭 0건 -->
      <template v-if="store.fallback || store.results.length === 0">
        <div class="card fallback-card">
          <p class="fallback-emoji">🤔</p>
          <h2 class="section-title" style="font-size: 17px">
            정확한 추천이 어렵습니다
          </h2>
          <p class="sub-text" style="margin-top: 8px">
            {{ store.fallbackMessage || '가까운 내과를 먼저 방문해 보세요.' }}
          </p>
          <button class="btn btn-primary" style="margin-top: 18px" @click="goFallbackHospitals">
            가까운 내과 찾기
          </button>
        </div>
      </template>

      <!-- 추천 결과 -->
      <template v-else>
        <h2 class="section-title" style="font-size: 18px; margin-top: 4px">
          입력하신 증상은<br />아래 진료과와 관련 있을 수 있어요
        </h2>

        <!-- AI 추론 안내: 규칙 사전에 없는 표현이라 AI가 진료과를 추론한 경우 -->
        <div v-if="store.source === 'ai'" class="ai-notice card">
          <span class="ai-chip">✨ AI 추론</span>
          <p>사전에 등록된 키워드로는 매칭되지 않아, AI가 증상을 분석해 진료과를 추천했어요.</p>
        </div>

        <div class="result-list">
          <button
            v-for="(r, i) in store.results"
            :key="r.department_id"
            class="result-card card"
            @click="selectDept(r)"
          >
            <div class="rank-row">
              <span class="rank-badge" :class="{ top: i === 0 }">{{ i + 1 }}순위</span>
              <span v-if="r.score !== null" class="score">매칭 점수 {{ r.score }}</span>
              <span v-else class="score score-ai">✨ AI 추론</span>
            </div>
            <div class="dept-name">{{ r.department }}</div>
            <!-- AI 추론: 근거 문장 / 규칙 매칭: 키워드 태그 -->
            <div v-if="r.ai_reason" class="keywords">
              <span class="reason-label">추천 근거</span>
              <span class="ai-reason">{{ r.ai_reason }}</span>
            </div>
            <div v-else class="keywords">
              <span class="reason-label">추천 근거</span>
              <span v-for="kw in r.matched_keywords" :key="kw" class="tag tag-blue">
                {{ kw }}
              </span>
            </div>
            <div class="cta-row">이 진료과 병원 찾기 ›</div>
          </button>
        </div>

        <button class="btn btn-outline" style="margin-top: 16px" @click="router.push({ name: 'symptom' })">
          증상 다시 입력하기
        </button>
      </template>

      <p class="disclaimer">
        본 결과는 진단이 아닌 참고용 정보입니다.<br />
        증상이 심하거나 지속되면 즉시 의료기관을 방문하세요.
      </p>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useRecommendStore } from '@/stores/recommend'

const router = useRouter()
const store = useRecommendStore()

onMounted(() => {
  // 새로고침·직접 접근으로 store가 비어 있으면 증상 입력으로 안내
  if (!store.symptomText && store.results.length === 0 && !store.fallback) {
    router.replace({ name: 'symptom' })
  }
})

function selectDept(result) {
  store.selectDepartment(result)
  router.push({ name: 'hospitals' })
}

function goFallbackHospitals() {
  // 폴백: 내과 우선 안내 → 내과 병원 리스트로 이동
  store.selectDepartment({ department: '내과', department_id: null, fallbackName: '내과' })
  router.push({ name: 'hospitals' })
}
</script>

<style scoped>
.symptom-summary {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  line-height: 1.5;
}
.fallback-card {
  text-align: center;
  padding: 28px 18px;
}
.fallback-emoji {
  font-size: 36px;
  margin-bottom: 10px;
}
.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}
.result-card {
  text-align: left;
  cursor: pointer;
  border: 1px solid var(--border);
  transition: border-color 0.15s;
  font-family: inherit;
}
.result-card:hover {
  border-color: var(--primary);
}
.rank-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rank-badge {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-sub);
  background: #eef0f4;
  padding: 4px 10px;
  border-radius: 999px;
}
.rank-badge.top {
  background: var(--primary);
  color: #fff;
}
.score {
  font-size: 12px;
  color: var(--text-sub);
}
.score-ai {
  color: var(--primary);
  font-weight: 700;
}
.ai-notice {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #f3f0ff;
  border: 1px solid #ddd2ff;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
}
.ai-chip {
  align-self: flex-start;
  font-size: 12px;
  font-weight: 700;
  color: #6b3fd6;
  background: #e7deff;
  padding: 3px 9px;
  border-radius: 999px;
}
.ai-reason {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
}
.dept-name {
  margin-top: 10px;
  font-size: 19px;
  font-weight: 800;
  color: var(--text);
}
.keywords {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.reason-label {
  font-size: 12px;
  color: var(--text-sub);
  margin-right: 2px;
}
.cta-row {
  margin-top: 14px;
  font-size: 14px;
  font-weight: 700;
  color: var(--primary);
}
</style>
