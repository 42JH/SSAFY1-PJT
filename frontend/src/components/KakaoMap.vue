<template>
  <div class="map-wrap" :style="{ height }">
    <!-- 컨테이너는 항상 표시 — display:none 상태로 지도를 만들면
         카카오가 크기를 0으로 계산해 타일이 일부만 렌더되는 버그가 생긴다 -->
    <div ref="mapEl" class="map-el"></div>
    <!-- SDK 로딩 실패 시 폴백 (오버레이) -->
    <div v-if="failed" class="map-fallback">
      <p>🗺️ 지도를 불러올 수 없어요</p>
      <p class="sub-text">{{ failMessage }}</p>
      <p class="sub-text">아래 병원 리스트로 확인해 주세요.</p>
    </div>
    <div v-else-if="!ready" class="map-loading"><div class="spinner"></div></div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { loadKakaoMaps } from '@/utils/kakaoLoader'


import goldPin from './gold-pin.png'
import silverPin from './silver-pin.png'
import bronzePin from './bronze-pin.png'

const RANK_MARKERS = [goldPin, silverPin, bronzePin]

const props = defineProps({
  center: { type: Object, required: true }, // { lat, lng }
  level: { type: Number, default: 5 },
  height: { type: String, default: '280px' },
  hospitals: { type: Array, default: () => [] }, // [{id, name, latitude, longitude, distance_km, is_open}]
  userLocation: { type: Object, default: null }, // { lat, lng }
  showDetailLink: { type: Boolean, default: true }, // 인포윈도우에 '상세 보기' 노출 여부
  highlightTop: { type: Number, default: 0 }, // 상위 N곳을 메달 마커로 강조 (0=비활성)
  path: { type: Array, default: null }, // 길찾기 경로 [[lat,lng],...]
})

const emit = defineEmits(['marker-click', 'marker-detail', 'map-click', 'map-error'])

const mapEl = ref(null)
const ready = ref(false)
const failed = ref(false)
const failMessage = ref('')

let kakao = null
let map = null
let markers = []
let clusterer = null
let polyline = null
let infowindow = null
let userOverlay = null
let resizeObserver = null

// 이 레벨 이상으로 축소되면 클러스터러가 마커를 묶음 개수로 표현한다.
const CLUSTER_MIN_LEVEL = 5

onMounted(async () => {
  try {
    kakao = await loadKakaoMaps()
    await nextTick() // 레이아웃 확정 후 생성 (컨테이너 크기 보장)
    map = new kakao.maps.Map(mapEl.value, {
      center: new kakao.maps.LatLng(props.center.lat, props.center.lng),
      level: props.level,
    })
    infowindow = new kakao.maps.InfoWindow({ removable: true })
    // 지도 빈 곳 클릭 → 좌표 전달 (위치 직접 설정 등에 활용)
    kakao.maps.event.addListener(map, 'click', (e) => {
      emit('map-click', { lat: e.latLng.getLat(), lng: e.latLng.getLng() })
    })
    // 클러스터러: 축소 시 마커를 개수 뱃지로 묶음 (확대 레벨 5부터 개별 표시)
    if (kakao.maps.MarkerClusterer) {
      clusterer = new kakao.maps.MarkerClusterer({
        map,
        averageCenter: true,
        minLevel: CLUSTER_MIN_LEVEL,
        disableClickZoom: false,
      })
    }
    ready.value = true
    // 생성 직후 크기 재계산 — 타일 부분 렌더 방지
    map.relayout()
    map.setCenter(new kakao.maps.LatLng(props.center.lat, props.center.lng))
    // 컨테이너 폭이 나중에 확정되면 타일이 절반만 그려짐(살구색 워터마크).
    // 크기가 바뀔 때마다 relayout + 중심 복원해서 메운다
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        if (!map) return
        const c = map.getCenter()
        map.relayout()
        map.setCenter(c)
      })
      resizeObserver.observe(mapEl.value)
    }
    renderMarkers()
    renderUserLocation()
    renderPath()
  } catch (err) {
    failed.value = true
    failMessage.value = err.message
    emit('map-error', err)
  }
})

// 창 크기·브레이크포인트 변경 시 타일 재계산 (반응형 분할 뷰 대응)
function onResize() {
  if (map) map.relayout()
}
window.addEventListener('resize', onResize)
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (resizeObserver) resizeObserver.disconnect()
})

watch(() => props.hospitals, () => {
  if (ready.value) renderMarkers()
})

watch(() => props.center, (c) => {
  if (ready.value && c) map.setCenter(new kakao.maps.LatLng(c.lat, c.lng))
})

watch(() => props.userLocation, () => {
  if (ready.value) renderUserLocation()
})

watch(() => props.path, () => {
  if (ready.value) renderPath()
})

function clearMarkers() {
  markers.forEach((m) => m.setMap(null))
  markers = []
  if (clusterer) clusterer.clear()
}

function openInfo(h, pos) {
  infowindow.setContent(buildInfoContent(h))
  infowindow.setPosition(pos)
  infowindow.open(map)
  emit('marker-click', h)
}

function renderMarkers() {
  clearMarkers()

  const bounds = new kakao.maps.LatLngBounds()
  let hasBounds = false

  const plainMarkers = []

  props.hospitals.forEach((h, idx) => {
    const pos = new kakao.maps.LatLng(h.latitude, h.longitude)

    let marker

    if (idx < 3) {
      const markerImage = new kakao.maps.MarkerImage(
        RANK_MARKERS[idx],
        new kakao.maps.Size(32, 43),
        {
          offset: new kakao.maps.Point(16, 43),
        }
      )

      marker = new kakao.maps.Marker({
        position: pos,
        title: h.name,
        image: markerImage,
      })
    } else {
      marker = new kakao.maps.Marker({
        position: pos,
        title: h.name,
      })
    }

    kakao.maps.event.addListener(marker, 'click', () => openInfo(h, pos))

    plainMarkers.push(marker)

    bounds.extend(pos)
    hasBounds = true
  })

  if (clusterer) {
    clusterer.addMarkers(plainMarkers)
  } else {
    plainMarkers.forEach((m) => m.setMap(map))
  }

  markers = plainMarkers

  if (props.userLocation) {
    bounds.extend(
      new kakao.maps.LatLng(
        props.userLocation.lat,
        props.userLocation.lng
      )
    )
    hasBounds = true
  }

  if (hasBounds && props.hospitals.length > 0) {
    map.setBounds(bounds, 30)
  }
}

function renderPath() {
  if (polyline) {
    polyline.setMap(null)
    polyline = null
  }
  if (!props.path || props.path.length < 2) return
  const latlngs = props.path.map(([lat, lng]) => new kakao.maps.LatLng(lat, lng))
  polyline = new kakao.maps.Polyline({
    map,
    path: latlngs,
    strokeWeight: 5,
    strokeColor: '#2f6bff',
    strokeOpacity: 0.85,
    strokeStyle: 'solid',
  })
  // 경로 전체가 보이도록 범위 맞춤
  const bounds = new kakao.maps.LatLngBounds()
  latlngs.forEach((p) => bounds.extend(p))
  map.setBounds(bounds, 40)
}

function buildInfoContent(h) {
  const wrap = document.createElement('div')
  wrap.style.cssText = 'padding:8px 12px;font-size:13px;min-width:160px;line-height:1.6;'

  const name = document.createElement('strong')
  name.textContent = h.name
  wrap.appendChild(name)

  const info = document.createElement('div')
  const dist = h.distance_km != null ? `${h.distance_km}km · ` : ''
  const status = document.createElement('span')
  status.textContent = h.is_open === false ? '영업종료' : h.is_open ? '영업중' : ''
  status.style.cssText = h.is_open ? 'color:#18a35a;font-weight:600;' : 'color:#6b7385;'
  info.append(dist, status)
  wrap.appendChild(info)

  if (props.showDetailLink) {
    const link = document.createElement('a')
    link.textContent = '상세 보기 →'
    link.style.cssText = 'color:#2f6bff;cursor:pointer;font-weight:600;'
    link.addEventListener('click', () => emit('marker-detail', h))
    wrap.appendChild(link)
  }
  return wrap
}

function renderUserLocation() {
  if (userOverlay) {
    userOverlay.setMap(null)
    userOverlay = null
  }
  if (!props.userLocation) return
  const pos = new kakao.maps.LatLng(props.userLocation.lat, props.userLocation.lng)
  // 현재 위치: 파란 점 커스텀 오버레이
  userOverlay = new kakao.maps.CustomOverlay({
    map,
    position: pos,
    content:
      '<div style="width:16px;height:16px;background:#2f6bff;border:3px solid #fff;border-radius:50%;box-shadow:0 0 6px rgba(47,107,255,.6);"></div>',
  })
}
</script>

<style scoped>
.map-wrap {
  position: relative;
  width: 100%;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
  background: #eef0f4;
}
.map-el {
  width: 100%;
  height: 100%;
}
.map-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.map-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  padding: 16px;
  font-weight: 600;
}
</style>
