/** 카카오맵 JavaScript SDK 동적 로더.
 *  키가 없거나 로딩 실패 시 reject → 호출부에서 리스트 뷰 폴백 처리.
 */
let loadPromise = null

export function loadKakaoMaps() {
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve, reject) => {
    const key = import.meta.env.VITE_KAKAO_JS_KEY
    if (!key) {
      reject(new Error('카카오맵 JavaScript 키가 설정되지 않았습니다. (.env의 VITE_KAKAO_JS_KEY)'))
      return
    }
    if (window.kakao?.maps) {
      resolve(window.kakao)
      return
    }

    const script = document.createElement('script')
    // clusterer: 마커 클러스터링 라이브러리 (NF03)
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${key}&autoload=false&libraries=clusterer`
    script.onerror = () => reject(new Error('카카오맵 SDK 로딩에 실패했습니다.'))
    script.onload = () => {
      window.kakao.maps.load(() => resolve(window.kakao))
    }
    document.head.appendChild(script)

    // 10초 타임아웃
    setTimeout(() => reject(new Error('카카오맵 SDK 로딩 시간 초과')), 10000)
  })

  loadPromise.catch(() => {
    loadPromise = null // 실패 시 재시도 가능하도록 초기화
  })

  return loadPromise
}
