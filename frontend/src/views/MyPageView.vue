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

        <!-- 건강 로그 -->
        <h3 class="block-title">📋 건강 로그 (증상 검색 이력)</h3>
        <div v-if="profile.logs.length" class="log-list">
          <div v-for="log in profile.logs" :key="log.id" class="card log-card">
            <div class="log-top">
              <span class="tag tag-blue">{{ log.recommended_dept }}</span>
              <span class="log-date">{{ log.searched_at }}</span>
            </div>
            <p class="log-text">{{ log.symptom_text }}</p>
            <button class="log-delete" @click="removeLog(log.id)">삭제</button>
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

import { client } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

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
.block-title {
  margin: 26px 0 12px;
  font-size: 15px;
  font-weight: 700;
}
.log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.log-card {
  position: relative;
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
.log-delete {
  margin-top: 10px;
  border: none;
  background: none;
  color: var(--text-sub);
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  padding: 4px 0;
}
</style>
