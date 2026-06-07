import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/symptom', name: 'symptom', component: () => import('@/views/SymptomInputView.vue') },
    { path: '/result', name: 'result', component: () => import('@/views/ResultView.vue') },
    {
      path: '/hospitals',
      name: 'hospitals',
      component: () => import('@/views/HospitalListView.vue'),
      meta: { wide: true }, // 데스크톱에서 지도+리스트 분할 뷰
    },
    { path: '/hospitals/:id', name: 'hospital-detail', component: () => import('@/views/HospitalDetailView.vue'), props: true },
    { path: '/emergency', name: 'emergency', component: () => import('@/views/EmergencyView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    { path: '/signup', name: 'signup', component: () => import('@/views/SignupView.vue') },
    {
      path: '/mypage',
      name: 'mypage',
      component: () => import('@/views/MyPageView.vue'),
      meta: { requiresAuth: true },
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

// 마이페이지는 로그인 필요 → 비로그인 시 로그인 화면으로
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('itdoc_access')) {
    return { name: 'login' }
  }
})

export default router
