
import {t as uiText, useI18n as useInterfaceLanguage, localeTag as uiLocaleTag} from '../space-design/i18n';
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faQrcode, faPrint } from '@fortawesome/free-solid-svg-icons'
import Overlay from './ui/Overlay'
import { issueMinarQrCards } from '../api'

// Minar Space QR kirish kartalari: guruh yoki bitta talaba uchun. Har yangi QR oldingisini bekor qiladi.
// `studentIds` berilsa — darhol shu talabalar uchun, aks holda guruh tanlanadi.
export default function MinarQrCards({ groups = [], groupsLoading = false, groupsError = '', onRetryGroups, studentIds = null, onClose }) {
  useInterfaceLanguage();
  const [groupId, setGroupId] = useState('')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)

  async function issue(body) {
    setBusy(true)
    try {
      const res = await issueMinarQrCards(body)
      if (!res.cards.length) toast(uiText("Bu guruhda kira oladigan Space hisobi yo'q"), { icon: 'ℹ️' })
      setData(res)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (studentIds?.length) issue({ student_ids: studentIds })
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  function print() {
    document.body.classList.add('printing-qr')
    const done = () => {
      document.body.classList.remove('printing-qr')
      window.removeEventListener('afterprint', done)
    }
    window.addEventListener('afterprint', done)
    window.print()
  }

  const cards = data?.cards || []
  return (
    <>
      <Overlay className="modal-overlay" onClick={onClose}>
        <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
          <div className="modal-header">
            <h3><FontAwesomeIcon icon={faQrcode} /> {uiText("QR kirish kartalari")}</h3>
            <button className="modal-close" onClick={onClose}>✕</button>
          </div>
          <div className="modal-body">
            <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>{uiText("O'quvchi telefon kamerasi bilan QR'ni skanerlasa, parolsiz kiradi va o'ziga yangi parol o'rnatadi. Har QR")}<strong>{uiText("bir marta")}</strong> {uiText("ishlaydi va")} {data?.expires_days || 14}{uiText("kun amal qiladi; yangisi chiqarilsa eskisi bekor bo'ladi.")}</p>
            {!studentIds && (
              <>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <label style={{ flex: 1 }}>{uiText("Guruh")}<select className="field" value={groupId} disabled={groupsLoading || !!groupsError || busy} onChange={e => setGroupId(e.target.value)}>
                    <option value="">{groupsLoading ? uiText("Guruhlar yuklanmoqda...") : uiText("Guruhni tanlang...")}</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </select>
                </label>
                <button className="button" disabled={!groups.some(g => String(g.id) === groupId) || busy || groupsLoading || !!groupsError} onClick={() => issue({ group_id: Number(groupId) })}>
                  {busy ? uiText("Yaratilmoqda...") : 'QR yaratish'}
                </button>
              </div>
              {groupsLoading && <p className="text-muted" role="status">{uiText("Guruhlar yuklanmoqda...")}</p>}
              {groupsError && <div role="alert"><p>{groupsError}</p><button className="button secondary" onClick={onRetryGroups}>{uiText("Qayta urinish")}</button></div>}
              {!groupsLoading && !groupsError && groups.length === 0 && <p className="text-muted" role="status">{uiText("Faol guruh topilmadi.")}</p>}
              </>
            )}
            {busy && studentIds && <div className="text-muted">{uiText("Yaratilmoqda...")}</div>}
            {cards.length > 0 && (
              <div className="qr-grid qr-grid-preview">
                {cards.map(c => <QrCard key={c.student_id} card={c} />)}
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button className="button secondary" onClick={onClose}>{uiText("Yopish")}</button>
            <button className="button" onClick={print} disabled={!cards.length}>
              <FontAwesomeIcon icon={faPrint} />{uiText("Chop etish")}</button>
          </div>
        </div>
      </Overlay>
      {cards.length > 0 && createPortal(
        <div className="qr-print-root">
          <div className="qr-grid">{cards.map(c => <QrCard key={c.student_id} card={c} />)}</div>
        </div>,
        document.body,
      )}
    </>
  )
}

function QrCard({ card }) {
  useInterfaceLanguage();
  return (
    <div className="qr-card">
      {/* SVG serverda (segno) bizning havoladan yasalgan — foydalanuvchi kiritmasi yo'q */}
      <div className="qr-svg" dangerouslySetInnerHTML={{ __html: card.svg }} />
      <strong>{card.full_name}</strong>
      <span>ID: {card.login_id}</span>
      <small>space.minaracademy.uz</small>
    </div>
  )
}
