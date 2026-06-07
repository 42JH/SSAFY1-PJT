<template>
  <div class="app-shell">
    <!-- 데스크톱 전용 브랜드 패널 (1024px 미만에서는 숨김) -->
    <aside class="brand-panel">
      <img src="/logo.svg" alt="잇닥" class="brand-logo" />
      <h1 class="brand-title">잇닥 <span>ITdoc</span></h1>
      <p class="brand-tagline">
        증상을 입력하면<br />
        진료과와 우리 동네 병원을<br />
        추천해 드려요
      </p>
      <ul class="brand-features">
        <li>✓ 키워드 점수화 기반 진료과 추천</li>
        <li>✓ 응급 신호 감지 시 119 안내</li>
        <li>✓ 구미권 실제 병·의원 554곳</li>
        <li>✓ 앱 안에서 지도·길찾기까지</li>
      </ul>
      <p class="brand-foot">잇닥의 추천은 진단이 아닌 참고용 정보입니다.</p>
    </aside>

    <div class="app-frame" :class="{ wide: route.meta.wide }">
      <RouterView />
    </div>
  </div>
</template>

<script setup>
import { RouterView, useRoute } from 'vue-router'

const route = useRoute()
</script>
