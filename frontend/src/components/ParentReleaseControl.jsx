import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowRotateRight, faArrowUpRightFromSquare, faCircleCheck, faCircleInfo,
  faCloudArrowUp, faMobileScreen, faPowerOff, faShieldHalved,
  faTriangleExclamation, faWrench,
} from '@fortawesome/free-solid-svg-icons'
import { toast } from 'react-hot-toast'
import { fetchParentReleaseConfig, updateParentReleaseConfig } from '../api'
import { PageIntro } from './ui/Workspace'
import useConfirm from './ui/useConfirm'
import './parent-release-control.css'

const PREVIEW_START_BUILD = 5

function toDraft(config) {
  return {
    maintenance_enabled: Boolean(config.maintenance_enabled),
    maintenance_title: config.maintenance_title,
    maintenance_message: config.maintenance_message,
    min_supported_build: String(config.min_supported_build),
    latest_build: String(config.latest_build),
    app_store_url: config.app_store_url,
  }
}

function isPositiveInteger(value) {
  return /^[1-9][0-9]*$/.test(value) && Number(value) <= 999999999
}

function draftError(draft) {
  if (!draft.maintenance_title.trim() || !draft.maintenance_message.trim()) return 'Texnik ko‘rik sarlavhasi va matnini kiriting.'
  if (!isPositiveInteger(draft.min_supported_build) || !isPositiveInteger(draft.latest_build)) return 'Build raqamlari musbat butun son bo‘lishi kerak.'
  if (Number(draft.latest_build) < Number(draft.min_supported_build)) return 'Oxirgi build minimal builddan kichik bo‘lishi mumkin emas.'
  if (!/^https:\/\/apps\.apple\.com\/[a-z]{2}\/app(?:\/[A-Za-z0-9-]+)?\/id6820518218$/.test(draft.app_store_url.trim())) return 'Minar Parents App Store havolasini kiriting.'
  return ''
}

function formatUpdatedAt(value) {
  if (!value) return 'Hali o‘zgartirilmagan'
  const date = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return 'Hali o‘zgartirilmagan'
  return new Intl.DateTimeFormat('uz-UZ', { timeZone: 'Asia/Tashkent', dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export default function ParentReleaseControl() {
  const [confirmUI, ask] = useConfirm()
  const [saved, setSaved] = useState(null)
  const [draft, setDraft] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [previewBuild, setPreviewBuild] = useState(PREVIEW_START_BUILD)

  async function load() {
    setLoading(true)
    setLoadError('')
    try {
      const config = await fetchParentReleaseConfig()
      setSaved(config)
      setDraft(toDraft(config))
    } catch (error) { setLoadError(error.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  function edit(key, value) {
    setDraft(current => ({ ...current, [key]: value }))
  }

  const validationError = draft ? draftError(draft) : ''
  const dirty = Boolean(saved && draft && JSON.stringify(toDraft(saved)) !== JSON.stringify(draft))
  const currentBuildStatus = !draft ? 'normal'
    : Number(draft.min_supported_build) > previewBuild ? 'update'
      : draft.maintenance_enabled ? 'maintenance' : 'normal'

  async function save() {
    if (!dirty || validationError || saving) return
    const enablingMaintenance = draft.maintenance_enabled && !saved.maintenance_enabled
    const raisingMinimum = Number(draft.min_supported_build) > saved.min_supported_build
    if (enablingMaintenance || raisingMinimum) {
      const accepted = await ask({
        title: enablingMaintenance ? 'Ilovani vaqtincha to‘xtatish' : 'Majburiy yangilanishni yoqish',
        message: enablingMaintenance
          ? 'Ota-onalar ilovada texnik ko‘rik ekranini ko‘radi. Eski versiyalar API so‘rovlari ham vaqtincha to‘xtaydi.'
          : `Build ${draft.min_supported_build} dan eski ilovalar bloklanadi. Yangi versiya App Store’da chiqib, havola ishlayotganini tekshiring.`,
        detail: 'O‘zgarish saqlangach darhol barcha ota-onalarga ta’sir qiladi.',
        confirmLabel: enablingMaintenance ? 'Ha, to‘xtatish' : 'Ha, talab qilish',
      })
      if (!accepted) return
    }
    setSaving(true)
    try {
      const next = await updateParentReleaseConfig({
        ...draft,
        maintenance_title: draft.maintenance_title.trim(),
        maintenance_message: draft.maintenance_message.trim(),
        min_supported_build: Number(draft.min_supported_build),
        latest_build: Number(draft.latest_build),
        app_store_url: draft.app_store_url.trim(),
      })
      setSaved(next)
      setDraft(toDraft(next))
      toast.success('Mobil ilova sozlamalari saqlandi')
    } catch (error) { toast.error(error.message) }
    finally { setSaving(false) }
  }

  return <div className="page parent-release-page">
    {confirmUI}
    <PageIntro
      eyebrow="OTA-ONA ILOVASI · RELEASE CONTROL"
      title={<>Mobil ilova boshqaruvi</>}
      description="Texnik ko‘rik, minimal build va App Store havolasini shu yerdan boshqaring."
      actions={<button className="button secondary" onClick={load} disabled={loading || saving || dirty} title={dirty ? 'Avval o‘zgarishlarni saqlang yoki bekor qiling' : undefined}><FontAwesomeIcon icon={faArrowRotateRight} /> Yangilash</button>}
    />

    {loading ? <div className="release-loading" role="status">Sozlamalar yuklanmoqda…</div>
      : loadError ? <div className="release-error" role="alert"><FontAwesomeIcon icon={faTriangleExclamation} /><div><strong>Sozlamalar yuklanmadi</strong><p>{loadError}</p></div><button className="button secondary" onClick={load}>Qayta urinish</button></div>
        : <>
          <div className="release-overview" aria-label="Joriy holat">
            <div className="release-overview-main">
              <span className={`release-live-dot ${saved.maintenance_enabled ? 'is-paused' : ''}`} />
              <div><small>HOZIRGI HOLAT</small><strong>{saved.maintenance_enabled ? 'Texnik ko‘rik yoqilgan' : 'Ilova ishlayapti'}</strong><span>Oxirgi o‘zgarish: {formatUpdatedAt(saved.updated_at)}</span></div>
            </div>
            <div className="release-overview-metric"><small>MINIMAL BUILD</small><strong>{saved.min_supported_build}</strong><span>Shundan eski versiyalar bloklanadi</span></div>
            <div className="release-overview-metric"><small>SO‘NGGI BUILD</small><strong>{saved.latest_build}</strong><span>CRM’da ko‘rsatilgan build</span></div>
          </div>

          <div className="release-grid">
            <div className="release-settings">
              <section className="release-panel">
                <header><span className="release-panel-icon"><FontAwesomeIcon icon={faWrench} /></span><div><h2>Texnik ko‘rik</h2><p>Faollashtirilsa ota-onalar ilovaga kira olmaydi. To‘lov callbacklari va CRM ishlashda davom etadi.</p></div></header>
                <label className="release-switch-row">
                  <span><strong>Ilovani vaqtincha to‘xtatish</strong><small>Oldingi versiyalarda ham server 503 javob beradi.</small></span>
                  <input type="checkbox" checked={draft.maintenance_enabled} onChange={event => edit('maintenance_enabled', event.target.checked)} disabled={saving} aria-label="Texnik ko‘rikni yoqish" />
                </label>
                <div className="release-fields">
                  <label><span>Sarlavha</span><input className="field" maxLength={120} value={draft.maintenance_title} onChange={event => edit('maintenance_title', event.target.value)} disabled={saving} /></label>
                  <label><span>Ota-onalarga ko‘rinadigan matn</span><textarea className="field" rows={3} maxLength={600} value={draft.maintenance_message} onChange={event => edit('maintenance_message', event.target.value)} disabled={saving} /></label>
                </div>
              </section>

              <section className="release-panel">
                <header><span className="release-panel-icon"><FontAwesomeIcon icon={faMobileScreen} /></span><div><h2>Versiyalar va majburiy yangilanish</h2><p>Build raqami Xcode’dagi <code>CFBundleVersion</code> bilan bir xil bo‘lishi kerak.</p></div></header>
                <div className="release-build-fields">
                  <label><span>Minimal qo‘llab-quvvatlanadigan build</span><input className="field" type="number" min="1" step="1" value={draft.min_supported_build} onChange={event => edit('min_supported_build', event.target.value)} disabled={saving} /><small>Past versiyalar yangilanishsiz kira olmaydi.</small></label>
                  <label><span>App Store’dagi so‘nggi build</span><input className="field" type="number" min="1" step="1" value={draft.latest_build} onChange={event => edit('latest_build', event.target.value)} disabled={saving} /><small>Minimal builddan kichik bo‘lmasin.</small></label>
                </div>
                <label className="release-url-field"><span>App Store havolasi</span><input className="field" type="url" value={draft.app_store_url} onChange={event => edit('app_store_url', event.target.value)} disabled={saving} /><small>Majburiy yangilanish tugmasi shu havolani ochadi.</small></label>
                <div className="release-note"><FontAwesomeIcon icon={faCircleInfo} /><span>Minimal buildni faqat yangi versiya App Store’da chiqib, havola ishlagach oshiring. Eski buildlarda yangilanish oynasi o‘rniga server xatosi ko‘rinishi mumkin.</span></div>
              </section>

              <div className="release-savebar">
                <span className={dirty ? 'is-dirty' : ''}><FontAwesomeIcon icon={dirty ? faCircleInfo : faCircleCheck} /> {dirty ? 'Saqlanmagan o‘zgarishlar' : 'Barcha o‘zgarishlar saqlangan'}</span>
                <div><button className="button secondary" onClick={() => setDraft(toDraft(saved))} disabled={!dirty || saving}>Bekor qilish</button><button className="button" onClick={save} disabled={!dirty || Boolean(validationError) || saving}><FontAwesomeIcon icon={faCloudArrowUp} /> {saving ? 'Saqlanmoqda…' : 'Saqlash'}</button></div>
              </div>
              {validationError && <p className="release-validation" role="alert">{validationError}</p>}
            </div>

            <aside className="release-preview" aria-label="Ilovadagi holatning oldindan ko‘rinishi">
              <div className="release-preview-head"><span>JONLI OLDINDAN KO‘RISH</span><label>Namuna build <input aria-label="Oldindan ko‘rish uchun build raqami" type="number" min="1" step="1" value={previewBuild} onChange={event => setPreviewBuild(Math.max(1, Number(event.target.value) || 1))} /></label></div>
              <div className="release-phone"><div className="release-phone-notch" /><div className={`release-phone-screen ${currentBuildStatus}`}>
                <span className="release-phone-brand"><FontAwesomeIcon icon={faShieldHalved} /> MINAR PARENTS</span>
                <div className="release-phone-center"><span className="release-phone-symbol"><FontAwesomeIcon icon={currentBuildStatus === 'normal' ? faCircleCheck : currentBuildStatus === 'update' ? faCloudArrowUp : faWrench} /></span>
                  <small>{currentBuildStatus === 'normal' ? 'XUSH KELIBSIZ' : currentBuildStatus === 'update' ? 'YANGI VERSIYA' : 'TEXNIK KO‘RIK'}</small>
                  <h3>{currentBuildStatus === 'normal' ? 'Ilova ishlayapti' : currentBuildStatus === 'update' ? 'Yangilash talab qilinadi' : draft.maintenance_title || 'Texnik ko‘rik'}</h3>
                  <p>{currentBuildStatus === 'normal' ? 'Ota-onalar barcha bo‘limlardan foydalanishi mumkin.' : currentBuildStatus === 'update' ? 'Davom etish uchun ilovaning so‘nggi versiyasini o‘rnating.' : draft.maintenance_message}</p>
                  {currentBuildStatus === 'update' && <span className="release-phone-cta">App Store’da yangilash <FontAwesomeIcon icon={faArrowUpRightFromSquare} /></span>}
                  {currentBuildStatus === 'maintenance' && <span className="release-phone-cta muted">Keyinroq qayta urinib ko‘ring</span>}
                </div><span className="release-phone-foot">MINAR ACADEMY</span>
              </div></div>
              <p className="release-preview-caption"><FontAwesomeIcon icon={faPowerOff} /> Bu ko‘rinish namuna build {previewBuild} uchun taxminiy. Yangi versiyada matnlar ilovada mos tarzda chiziladi.</p>
              <a href={saved.app_store_url} target="_blank" rel="noopener noreferrer" className="release-store-link">App Store sahifasini tekshirish <FontAwesomeIcon icon={faArrowUpRightFromSquare} /></a>
            </aside>
          </div>
        </>}
  </div>
}
