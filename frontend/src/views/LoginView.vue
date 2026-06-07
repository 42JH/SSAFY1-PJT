<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.push({ name: 'home' })">‹</button>
      <h1>로그인</h1>
    </header>

    <div class="page">
      <h2 class="section-title">다시 만나서 반가워요 👋</h2>
      <p class="sub-text" style="margin-top: 6px">
        로그인하면 증상 검색 이력이 건강 로그로 저장돼요.
      </p>

      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>이메일</span>
          <input v-model="email" type="email" required placeholder="you@example.com" />
        </label>
        <label class="field">
          <span>비밀번호</span>
          <input v-model="password" type="password" required placeholder="8자 이상" />
        </label>

        <p v-if="error" class="error-text">{{ error }}</p>

        <button class="btn btn-primary" type="submit" :disabled="loading">
          {{ loading ? '로그인 중...' : '로그인' }}
        </button>
      </form>

      <p class="switch-text">
        아직 계정이 없으신가요?
        <RouterLink :to="{ name: 'signup' }">회원가입</RouterLink>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(email.value, password.value)
    router.push({ name: 'mypage' })
  } catch (err) {
    error.value = err.response?.data?.detail ?? '로그인에 실패했습니다.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-form {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-sub);
}
.field input {
  border: 1.5px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  font-size: 15px;
  outline: none;
  background: var(--card);
  color: var(--text);
}
.field input:focus {
  border-color: var(--primary);
}
.error-text {
  color: var(--danger);
  font-size: 13px;
}
.switch-text {
  margin-top: 18px;
  text-align: center;
  font-size: 14px;
  color: var(--text-sub);
}
.switch-text a {
  color: var(--primary);
  font-weight: 700;
}
</style>
