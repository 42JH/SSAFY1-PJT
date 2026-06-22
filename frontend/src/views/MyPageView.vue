<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.push({ name: 'home' })">‹</button>
      <h1>마이페이지</h1>
    </header>

    <div class="page">
      <div v-if="loading" style="padding: 60px 0"><div class="spinner"></div></div>

      <template v-else-if="profile">
        <!-- 프로필 -->
        <div class="card profile-card">
          <div class="avatar">{{ profile.nickname?.slice(0, 1) ?? '잇' }}</div>
          <div>
            <p class="nickname">{{ profile.nickname }}</p>
            <p class="sub-text">{{ profile.email }} · {{ profile.joined_at }} 가입</p>
          </div>
        </div>

        <!-- 인사이트 요약 -->
        <div v-if="profile.stats?.total" class="stat-row">
          <div class="card stat-card">
            <span class="stat-num">{{ profile.stats.total }}</span>
            <span class="stat-label">총 검색</span>
          </div>
          <div class="card stat-card">
            <span class="stat-num">{{ profile.stats.this_month }}</span>
            <span class="stat-label">이번 달</span>
          </div>
          <div class="card stat-card">
            <span class="stat-num stat-dept">{{ profile.stats.top_dept ?? '–' }}</span>
            <span class="stat-label">최다 추천과</span>
          </div>
        </div>

        <!-- 건강 로그 -->
        <h3 class="block-title">📋 건강 로그 (증상 검색 이력)</h3>
        <p class="log-guide">추천이 정확했는지 평가하면 다른 분들의 추천도 더 정확해져요.</p>
        <div v-if="profile.logs.length" class="log-list">
          <div v-for="log in profile.logs" :key="log.id" class="card log-card">
            <div class="log-top">
              <span class="tag tag-blue">{{ log.recommended_dept }}</span>
              <span class="log-date">{{ log.searched_at }}</span>
            </div>
            <p class="log-text">{{ log.symptom_text }}</p>

            <div class="log-actions">
              <button class="act-btn" @click="research(log)">🔁 다시 검색</button>
              <div class="vote">
                <button
                  class="vote-btn"
                  :class="{ on: log.feedback === 1 }"
                  title="추천이 정확했어요"
                  @click="vote(log, 1)"
                >👍</button>
                <button
                  class="vote-btn"
                  :class="{ on: log.feedback === -1 }"
                  title="추천이 맞지 않았어요"
                  @click="vote(log, -1)"
                >👎</button>
              </div>
              <button class="log-delete" @click="removeLog(log.id)">삭제</button>
            </div>
          </div>
        </div>
        <div v-else class="card" style="text-align: center; padding: 26px">
          <p class="sub-text">아직 검색 이력이 없어요.<br />증상을 검색하면 자동으로 기록됩니다.</p>
        </div>

        <button class="btn btn-outline" style="margin-top: 20px" @click="logout">
          로그아웃
        </button>
      </template>

      <p class="disclaimer">건강 로그는 참고용 기록이며 진단 정보가 아닙니다.</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { client, sendLogFeedback } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useRecommendStore } from '@/stores/recommend'

const router = useRouter()
const auth = useAuthStore()
const recommend = useRecommendStore()

const profile = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const { data } = await client.get('/auth/me/')
    profile.value = data
  } catch {
    auth.logout()
    router.replace({ name: 'login' })
  } finally {
    loading.value = false
  }
})

async function removeLog(id) {
  try {
    await client.delete(`/auth/logs/${id}/`)
    profile.value.logs = profile.value.logs.filter((l) => l.id !== id)
  } catch {
    /* 삭제 실패 시 무시 */
  }
}

// 같은 평가를 다시 누르면 취소(0), 아니면 해당 값으로 변경
async function vote(log, value) {
  const next = log.feedback === value ? 0 : value
  const prev = log.feedback
  log.feedback = next || null // 낙관적 업데이트
  try {
    await sendLogFeedback(log.id, next)
  } catch {
    log.feedback = prev // 실패 시 롤백
  }
}

// 이 증상으로 추천 흐름을 다시 실행 (학습된 가중치가 반영된 최신 추천)
async function research(log) {
  try {
    const data = await recommend.submitSymptom(log.symptom_text)
    router.push({ name: data.emergency ? 'emergency' : 'result' })
  } catch {
    /* 에러는 recommend.error로 표시되며, 이 화면에선 무시 */
  }
}

function logout() {
  auth.logout()
  router.push({ name: 'home' })
}
</script>

<style scoped>
.profile-card {
  display: flex;
  align-items: center;
  gap: 14px;
}
.avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 22px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.nickname {
  font-size: 17px;
  font-weight: 800;
}
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 16px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 8px;
  text-align: center;
}
.stat-num {
  font-size: 20px;
  font-weight: 800;
  color: var(--primary);
}
.stat-dept {
  font-size: 15px;
}
.stat-label {
  font-size: 12px;
  color: var(--text-sub);
}
.block-title {
  margin: 26px 0 4px;
  font-size: 15px;
  font-weight: 700;
}
.log-guide {
  font-size: 12.5px;
  color: var(--text-sub);
  margin-bottom: 12px;
}
.log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.log-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.log-date {
  font-size: 12px;
  color: var(--text-sub);
}
.log-text {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.5;
}
.log-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.act-btn {
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
}
.act-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.vote {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.vote-btn {
  border: 1px solid var(--border);
  background: var(--card);
  font-size: 14px;
  line-height: 1;
  border-radius: 8px;
  padding: 6px 9px;
  cursor: pointer;
  filter: grayscale(1);
  opacity: 0.6;
  transition: all 0.12s;
}
.vote-btn.on {
  filter: none;
  opacity: 1;
  border-color: var(--primary);
  background: var(--primary-light);
}
.log-delete {
  border: none;
  background: none;
  color: var(--text-sub);
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  padding: 4px 0;
}
</style>
