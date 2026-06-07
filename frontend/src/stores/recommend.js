import { defineStore } from 'pinia'

import { postRecommend } from '@/api/client'

/** 증상 입력 → 진료과 추천 흐름의 상태 관리 */
export const useRecommendStore = defineStore('recommend', {
  state: () => ({
    symptomText: '',
    loading: false,
    error: null,
    // 추천 응답
    emergency: false,
    emergencyKeywords: [],
    results: [],
    fallback: false,
    fallbackMessage: '',
    // 선택된 진료과 (병원 추천으로 이동 시)
    selectedDepartment: null,
  }),
  actions: {
    async submitSymptom(text) {
      this.symptomText = text
      this.loading = true
      this.error = null
      try {
        const { data } = await postRecommend(text)
        this.emergency = data.emergency
        this.emergencyKeywords = data.matched_keywords ?? []
        this.results = data.results ?? []
        this.fallback = data.fallback ?? false
        this.fallbackMessage = data.message ?? ''
        return data
      } catch (err) {
        this.error = '추천 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.'
        throw err
      } finally {
        this.loading = false
      }
    },
    selectDepartment(dept) {
      this.selectedDepartment = dept
    },
  },
})
