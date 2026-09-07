import { useCallback, useRef, useState } from 'react'
import ConfirmDialog from './ConfirmDialog'

/**
 * `window.confirm()` o'rniga — va'da (promise) qaytaradigan tasdiqlash oynasi.
 *
 * Nima uchun: ilovada 20 dan ortiq joyda brauzerning bezaksiz `confirm()`i
 * ishlatilardi. Uni <ConfirmDialog> ga o'tkazish har bir joyda holat (state),
 * "qaysi element o'chirilyapti" va yopish mantiqini qo'lda yozishni talab
 * qilardi — shuning uchun ko'p joyda umuman o'tkazilmasdi. Bu hook o'sha
 * ishni bir qatorga tushiradi va chaqiruv shakli `confirm()` bilan bir xil
 * qoladi:
 *
 *   const [confirmUI, ask] = useConfirm()
 *   ...
 *   if (!await ask({ title: "O'chirish", message: `"${x.name}" o'chirilsinmi?` })) return
 *   ...
 *   return <>{confirmUI} ...</>
 *
 * `danger` sukut bo'yicha true — bu oyna deyarli har doim buzuvchi amal uchun.
 * Qaytarib bo'lmaydigan amallar uchun `requireText` bering.
 */
export default function useConfirm() {
  const [opts, setOpts] = useState(null)
  const resolver = useRef(null)

  const ask = useCallback((options = {}) => {
    setOpts(options)
    return new Promise(resolve => { resolver.current = resolve })
  }, [])

  function settle(value) {
    setOpts(null)
    resolver.current?.(value)
    resolver.current = null
  }

  // `.confirm-layer` — tasdiqlash oynasi HAR DOIM ustida turishi uchun.
  // Bu hook ba'zan modal yoki yon panel ICHIDA chaqiriladi (masalan Leads'ning
  // bosqich boshqaruvida); ikkalasi ham z-index:1000 bo'lgani uchun DOM
  // tartibiga qarab tasdiq oynasi ostida qolib ketishi mumkin edi.
  const node = (
    <div className="confirm-layer">
    <ConfirmDialog
      open={!!opts}
      title={opts?.title || 'Tasdiqlaysizmi?'}
      message={opts?.message}
      detail={opts?.detail}
      confirmLabel={opts?.confirmLabel || 'Ha, davom etish'}
      cancelLabel={opts?.cancelLabel || 'Bekor'}
      danger={opts?.danger !== false}
      requireText={opts?.requireText || null}
      onConfirm={() => settle(true)}
      onClose={() => settle(false)}
    />
    </div>
  )

  return [node, ask]
}
