<template>
  <div>
    <!-- 뒤로가기는 히스토리(back)가 아닌 논리적 부모(홈)로 — result↔symptom 핑퐁 방지 -->
    <header class="page-header">
      <button class="back-btn" @click="router.push({ name: 'home' })">‹</button>
      <h1>증상 입력</h1>
    </header>

    <div class="page">
      <h2 class="section-title">어떤 증상이 있으신가요?</h2>
      <p class="sub-text" style="margin-top: 6px">
        느끼는 그대로 자유롭게 적어 주세요.
      </p>

      <div class="card" style="margin-top: 18px">
        <textarea
          v-model="text"
          class="symptom-input"
          rows="6"
          maxlength="300"
          placeholder="예: 어제부터 목이 붓고 침 삼킬 때 아파요. 콧물도 나요."
        ></textarea>
        <div class="char-count">{{ text.length }} / 300</div>
      </div>

      <!-- 입력 예시 힌트 -->
      <p class="hint-title">이런 증상이 있으신가요?</p>
      <div class="hint-chips">
        <button
          v-for="hint in hints"
          :key="hint"
          class="hint-chip"
          @click="appendHint(hint)"
        >
          {{ hint }}
        </button>
      </div>

      <p v-if="store.error" class="error-text">{{ store.error }}</p>

      <div style="margin-top: auto; padding-top: 24px">
        <button
          class="btn btn-primary"
          :disabled="!text.trim() || store.loading"
          @click="submit"
        >
          <span v-if="store.loading" class="btn-spinner"></span>
          {{ store.loading ? '분석 중...' : '추천 받기' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useRecommendStore } from '@/stores/recommend'

const router = useRouter()
const store = useRecommendStore()

const text = ref(store.symptomText)
const hints = ['목 아픔', '기침', '콧물', '발열', '복통', '어지럼증', '두통']

function appendHint(hint) {
  text.value = text.value ? `${text.value}, ${hint}` : hint
}

async function submit() {
  try {
    const data = await store.submitSymptom(text.value.trim())
    if (data.emergency) {
      router.push({ name: 'emergency' })
    } else {
      router.push({ name: 'result' })
    }
  } catch {
    /* 에러는 store.error로 표시 */
  }
}
</script>

<style scoped>
.symptom-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  line-height: 1.6;
  font-family: inherit;
  color: var(--text);
}
.char-count {
  text-align: right;
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 8px;
}
.hint-title {
  margin: 22px 0 10px;
  font-size: 14px;
  font-weight: 700;
}
.hint-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.hint-chip {
  padding: 9px 14px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card);
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  min-height: 38px;
}
.hint-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.error-text {
  margin-top: 14px;
  color: var(--danger);
  font-size: 13px;
}
.btn-spinner {
  width: 18px;
  height: 18px;
  border: 3px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
</style>
