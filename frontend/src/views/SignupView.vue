<template>
  <div>
    <header class="page-header">
      <button class="back-btn" @click="router.back()">‹</button>
      <h1>회원가입</h1>
    </header>

    <div class="page">
      <h2 class="section-title">잇닥과 함께해요 🩺</h2>
      <p class="sub-text" style="margin-top: 6px">
        가입하면 증상 검색 이력을 건강 로그로 관리할 수 있어요.
      </p>

      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>이메일</span>
          <input v-model="email" type="email" required placeholder="you@example.com" />
        </label>
        <label class="field">
          <span>닉네임</span>
          <input v-model="nickname" type="text" required maxlength="30" placeholder="잇닥이" />
        </label>
        <label class="field">
          <span>비밀번호</span>
          <input v-model="password" type="password" required minlength="8" placeholder="8자 이상" />
          <small v-if="password && password.length < 8" class="inline-error">
            비밀번호는 8자 이상이어야 해요.
          </small>
        </label>
        <label class="field">
          <span>비밀번호 확인</span>
          <input v-model="password2" type="password" required placeholder="한 번 더 입력" />
          <small v-if="password2 && password !== password2" class="inline-error">
            비밀번호가 일치하지 않아요.
          </small>
        </label>

        <p v-if="error" class="error-text">{{ error }}</p>

        <button class="btn btn-primary" type="submit" :disabled="loading || !canSubmit">
          {{ loading ? '가입 중...' : '가입하기' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const nickname = ref('')
const password = ref('')
const password2 = ref('')
const error = ref('')
const loading = ref(false)

const canSubmit = computed(
  () => email.value && nickname.value && password.value.length >= 8 && password.value === password2.value,
)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await auth.signup(email.value, password.value, nickname.value)
    router.push({ name: 'mypage' })
  } catch (err) {
    const data = err.response?.data
    error.value = data?.email?.[0] ?? data?.password?.[0] ?? data?.detail ?? '가입에 실패했습니다.'
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
.inline-error {
  color: var(--danger);
  font-weight: 400;
}
.error-text {
  color: var(--danger);
  font-size: 13px;
}
</style>
