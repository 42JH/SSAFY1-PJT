<template>
  <div class="page">
    <header class="home-header">
      <div class="logo">
        <img src="/logo.svg" alt="잇닥 로고" class="logo-img" />
        잇닥
      </div>
      <RouterLink v-if="auth.isLoggedIn" :to="{ name: 'mypage' }" class="auth-link">
        👤 {{ auth.user?.nickname }}
      </RouterLink>
      <RouterLink v-else :to="{ name: 'login' }" class="auth-link">로그인</RouterLink>
    </header>

    <h2 class="section-title">어디가 불편하세요?</h2>
    <p class="sub-text" style="margin-top: 6px">
      증상을 입력하면 진료과와 가까운 병원을 추천해 드려요.
    </p>

    <!-- 증상 입력 CTA — 입력창처럼 크게 -->
    <RouterLink to="/symptom" class="search-cta card">
      <p class="search-placeholder">
        예: 어제부터 목이 붓고<br />침 삼킬 때 아파요...
      </p>
      <span class="search-btn">🔍 증상 입력하고 추천받기</span>
    </RouterLink>

    <!-- 진료과 바로가기: 인기 4개 + 더보기 -->
    <div class="dept-head">
      <h3 class="block-title">진료과 바로가기</h3>
      <button class="more-btn" @click="showAllDepts = !showAllDepts">
        {{ showAllDepts ? '접기 ▲' : '더보기 ▼' }}
      </button>
    </div>
    <div class="dept-grid">
      <button
        v-for="d in visibleDepartments"
        :key="d.id"
        class="dept-chip"
        @click="goHospitals(d)"
      >
        <span class="dept-icon">{{ d.icon }}</span>
        <span>{{ d.name }}</span>
      </button>
    </div>

    <!-- 응급 배너 -->
    <RouterLink to="/emergency" class="emergency-banner">
      <span class="emergency-icon">🚨</span>
      <span>
        <strong>응급 상황인가요?</strong><br />
        <small>지금 즉시 119 안내 보기</small>
      </span>
      <span class="arrow">›</span>
    </RouterLink>

    <p class="disclaimer">
      잇닥의 추천은 진단이 아닌 참고용 정보입니다.<br />
      정확한 진단은 반드시 의료진과 상담하세요.
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { getDepartments } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useRecommendStore } from '@/stores/recommend'

const router = useRouter()
const store = useRecommendStore()
const auth = useAuthStore()

const ICONS = {
  내과: '💊', 이비인후과: '👂', 정형외과: '🦴', 피부과: '🧴',
  안과: '👁️', 신경과: '🧠', 외과: '🩹', 소아청소년과: '🧒',
  산부인과: '🤰', 비뇨의학과: '🚻', 정신건강의학과: '🍀', 치과: '🦷',
  신경외과: '🏥', 마취통증의학과: '💉', 재활의학과: '🤸', 가정의학과: '🏠',
}

// 사람들이 자주 찾는 진료과 — 첫 줄(4개)에 고정 노출
const POPULAR = ['내과', '이비인후과', '정형외과', '피부과']

const departments = ref([])
const showAllDepts = ref(false)

const visibleDepartments = computed(() => {
  const popular = POPULAR
    .map((name) => departments.value.find((d) => d.name === name))
    .filter(Boolean)
  if (!showAllDepts.value) return popular
  const rest = departments.value.filter((d) => !POPULAR.includes(d.name))
  return [...popular, ...rest]
})

onMounted(async () => {
  try {
    const { data } = await getDepartments()
    departments.value = data.map((d) => ({ ...d, icon: ICONS[d.name] ?? '🏥' }))
  } catch {
    departments.value = []
  }
})

function goHospitals(dept) {
  store.selectDepartment({ department_id: dept.id, department: dept.name })
  router.push({ name: 'hospitals' })
}
</script>

<style scoped>
.home-header {
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo {
  font-size: 22px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo-img {
  width: 34px;
  height: 34px;
}
.auth-link {
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--primary-light);
}

/* 증상 입력 CTA — 입력창 느낌으로 크게 */
.search-cta {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  text-decoration: none;
  padding: 20px 18px;
  border: 1.5px solid var(--border);
  transition: border-color 0.15s;
}
.search-cta:hover {
  border-color: var(--primary);
}
.search-placeholder {
  min-height: 64px;
  font-size: 15px;
  line-height: 1.6;
  color: #aab2c4;
}
.search-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 50px;
  border-radius: 12px;
  background: var(--primary);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
}

.dept-head {
  margin: 28px 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.block-title {
  font-size: 16px;
  font-weight: 700;
}
.more-btn {
  border: none;
  background: none;
  color: var(--text-sub);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 8px;
}
.more-btn:hover {
  color: var(--primary);
}
.dept-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.dept-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 4px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
  min-height: 44px;
}
.dept-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.dept-icon {
  font-size: 20px;
}

.emergency-banner {
  margin-top: 28px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--danger-light);
  border: 1px solid #f6c9c9;
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--danger);
}
.emergency-icon {
  font-size: 22px;
}
.emergency-banner small {
  color: #b06262;
}
.emergency-banner .arrow {
  margin-left: auto;
  font-size: 22px;
}
</style>
