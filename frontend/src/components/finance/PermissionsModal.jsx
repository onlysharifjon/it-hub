import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { finance } from '../../api'
import Modal from '../ui/Modal'
import { FormSkeleton } from '../ui/States'

/** Admin: "Finans" rolidagi xodimning moliya huquqlari. */
export default function PermissionsModal({ user, onClose }) {
  const [catalog, setCatalog] = useState(null)
  const [perms, setPerms] = useState([])
  const [isDefault, setIsDefault] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!user) return
    setCatalog(null)
    Promise.all([finance.me(), finance.userPermissions(user.id)])
      .then(([me, p]) => { setCatalog(me.catalog); setPerms(p.permissions); setIsDefault(p.is_default) })
      .catch(e => { toast.error(e.message); onClose() })
  }, [user])

  async function save(reset) {
    setBusy(true)
    try {
      const r = await finance.setUserPermissions(user.id, reset ? null : perms)
      setPerms(r.permissions); setIsDefault(r.is_default)
      toast.success('Huquqlar saqlandi — xodim keyingi sahifa yuklanishida ko‘radi')
      if (!reset) onClose()
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }

  const toggle = k => setPerms(p => (p.includes(k) ? p.filter(x => x !== k) : [...p, k]))
  return (
    <Modal open={!!user} onClose={onClose} title={`Moliya huquqlari — ${user?.full_name || user?.username || ''}`} size="md"
      footer={<>
        <button className="button secondary" disabled={busy} onClick={() => save(true)}>Standartga qaytarish</button>
        <button className="button" disabled={busy || !catalog} onClick={() => save(false)}>Saqlash</button>
      </>}>
      {!catalog ? <FormSkeleton fields={6} /> : (
        <>
          <p className="fin-note">Har bir imkoniyat alohida beriladi. Finans xodimi rollar, tizim sozlamalari va o'z huquqlarini o'zgartira olmaydi.
            {isDefault ? ' Hozir standart to‘plam qo‘llanmoqda.' : ''}</p>
          <div className="fin-perm-list">
            {catalog.map(c => (
              <label key={c.key} className="fin-check">
                <input type="checkbox" checked={perms.includes(c.key)} onChange={() => toggle(c.key)} />
                <span>{c.label}{c.default ? '' : <span className="muted-sm"> · qo'shimcha ruxsat</span>}</span>
              </label>
            ))}
          </div>
        </>
      )}
    </Modal>
  )
}
