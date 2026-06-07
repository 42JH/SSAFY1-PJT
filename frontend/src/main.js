import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { loadKakaoMaps } from './utils/kakaoLoader'
import './assets/main.css'

// 카카오맵 SDK 프리로드 — 지도 화면 진입 전에 미리 받아둠 (실패해도 무시, 화면에서 폴백 처리)
loadKakaoMaps().catch(() => {})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
