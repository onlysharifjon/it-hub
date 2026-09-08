import { PageIntro } from './ui/Workspace'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faPen, faTrash, faTag, faToggleOn, faToggleOff } from '@fortawesome/free-solid-svg-icons'
import { fetchTariffs, createTariff, updateTariff, deleteTariff } from '../api'
import DataTable from './ui/DataTable'
import Modal from './ui/Modal'
import ConfirmDialog from './ui/ConfirmDialog'
import Badge from './ui/Badge'
import { Input, Textarea } from './ui/Field'
import Catalog from './ui/Catalog'

const EMPTY = { name: '', price: '100000', description: '' }

export default function Tariffs() {
  const [tariffs, setTariffs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [confirmTarget, setConfirmTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try { setTariffs(await fetchTariffs()) }
    catch (e) { setError(e) }
    finally { setLoading(false) }
  }

  function openAdd() { setForm(EMPTY); setErrors({}); setModal('add') }
  function openEdit(t) {
    setForm({ name: t.name, price: String(t.price), description: t.description || '' })
    setErrors({})
    setModal(t)
  }
  function closeModal() { setModal(null); setErrors({}) }

  function validate() {
    const next = {}
    if (!form.name.trim()) next.name = 'Tarif nomini kiriting'
    if (!form.price) next.price = 'Narxni kiriting'
    else if (parseFloat(form.price) <= 0) next.price = "Narx musbat bo'lishi kerak"
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSave() {
    if (!validate()) return
    setSaving(true)
    try {
      const payload = { name: form.name, price: parseFloat(form.price), description: form.description || null }
      if (modal === 'add') {
        await createTariff(payload)
        toast.success("Tarif qo'shildi")
      } else {
        await updateTariff(modal.id, payload)
        toast.success('Saqlandi')
      }
      closeModal()
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteTariff(confirmTarget.id)
      toast.success("O'chirildi")
      setConfirmTarget(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setDeleting(false) }
  }

  async function handleToggle(t) {
    try {
      await updateTariff(t.id, { is_active: !t.is_active })
      load()
    } catch { toast.error('Xatolik') }
  }

  const columns = [
    {
      key: 'index', header: '#', width: 56, className: 'text-muted',
      render: (_row, i) => i + 1,
    },
    {
      key: 'name', header: 'Tarif nomi', sortable: true,
      render: t => <strong>{t.name}</strong>,
    },
    {
      key: 'price', header: "Narx (so'm/oy)", sortable: true, className: 'amount',
      sortValue: t => Number(t.price),
      render: t => `${Number(t.price).toLocaleString('uz-UZ')} so'm`,
    },
    {
      key: 'description', header: 'Tavsif',
      render: t => t.description || <span className="text-muted">—</span>,
    },
    {
      key: 'is_active', header: 'Holat', sortable: true,
      render: t => (
        <Badge variant={t.is_active ? 'success' : 'neutral'}>
          {t.is_active ? 'Faol' : 'Nofaol'}
        </Badge>
      ),
    },
    {
      key: 'actions', header: 'Amallar', className: 'actions',
      render: t => (
        <>
          <button
            className="btn-icon" onClick={() => handleToggle(t)}
            title={t.is_active ? 'Nofaol qilish' : 'Faol qilish'}
            aria-label={t.is_active ? 'Nofaol qilish' : 'Faol qilish'}
          >
            <FontAwesomeIcon icon={t.is_active ? faToggleOn : faToggleOff} />
          </button>
          <button className="btn-icon" onClick={() => openEdit(t)} title="Tahrirlash" aria-label="Tahrirlash">
            <FontAwesomeIcon icon={faPen} />
          </button>
          <button className="btn-icon danger" onClick={() => setConfirmTarget(t)} title="O'chirish" aria-label="O'chirish">
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </>
      ),
    },
  ]

  return (
    <div className="page">
      <PageIntro title={<>Tariflar</>} description={<>Guruhga biriktiriladigan oylik narxlar</>} actions={<><div className="header-actions">
          <button className="button" onClick={openAdd}>
            <FontAwesomeIcon icon={faPlus} /> Tarif qo'shish
          </button>
        </div></>} />

      <Catalog rows={tariffs} loading={loading} error={error} label="ta tarif" renderCard={(t, i) => (
        <article key={t.id} className={`catalog-card tariff-card${t.is_active ? '' : ' is-inactive'}`}>
          <div className="catalog-card-top"><span className="catalog-icon"><FontAwesomeIcon icon={faTag} /></span><Badge variant={t.is_active ? 'success' : 'neutral'}>{t.is_active ? 'Faol' : 'Nofaol'}</Badge></div>
          <span className="catalog-eyebrow">OYLIK TARIF · {String(i + 1).padStart(2, '0')}</span>
          <h2>{t.name}</h2>
          <div className="catalog-price">{Number(t.price).toLocaleString('uz-UZ')}<span>so‘m / oy</span></div>
          <p className="catalog-description">{t.description || 'Guruhlar uchun oylik to‘lov'}</p>
          <div className="catalog-card-footer">
            <button className="button secondary small" onClick={() => openEdit(t)}><FontAwesomeIcon icon={faPen} /> Tahrirlash</button>
            <button className="btn-icon" onClick={() => handleToggle(t)} aria-label={t.is_active ? 'Nofaol qilish' : 'Faol qilish'} title={t.is_active ? 'Nofaol qilish' : 'Faol qilish'}><FontAwesomeIcon icon={t.is_active ? faToggleOn : faToggleOff} /></button>
            <button className="btn-icon danger" onClick={() => setConfirmTarget(t)} aria-label="O‘chirish" title="O‘chirish"><FontAwesomeIcon icon={faTrash} /></button>
          </div>
        </article>
      )}>
      <DataTable
        columns={columns}
        rows={tariffs}
        loading={loading}
        error={error}
        onRetry={load}
        rowClassName={t => (!t.is_active ? 'row-inactive' : undefined)}
        empty={{
          icon: faTag,
          title: "Tariflar yo'q",
          description: "Guruhlarga narx biriktirish uchun birinchi tarifni qo'shing.",
          action: (
            <button className="button" onClick={openAdd}>
              <FontAwesomeIcon icon={faPlus} /> Tarif qo'shish
            </button>
          ),
        }}
      />

      </Catalog>

      <Modal
        open={!!modal}
        title={modal === 'add' ? 'Yangi tarif' : 'Tarifni tahrirlash'}
        onClose={closeModal}
        footer={
          <>
            <button className="button secondary" onClick={closeModal}>Bekor</button>
            <button className="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Input
          label="Tarif nomi" required
          value={form.name}
          error={errors.name}
          onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
          placeholder="Masalan: Standart, Premium, 3 oylik..."
        />
        <Input
          label="Narx (so'm/oy)" required type="number" min="1"
          value={form.price}
          error={errors.price}
          onChange={e => setForm(p => ({ ...p, price: e.target.value }))}
          placeholder="100000"
        />
        <Textarea
          label="Tavsif" rows={2}
          value={form.description}
          onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
          placeholder="Qo'shimcha ma'lumot..."
        />
      </Modal>

      <ConfirmDialog
        open={!!confirmTarget}
        title="Tarifni o'chirish"
        message={confirmTarget ? `"${confirmTarget.name}" tarifi o'chirilsinmi?` : ''}
        detail="Bu tarif biriktirilgan guruhlar narxsiz qolishi mumkin."
        confirmLabel="Ha, o'chirish"
        loading={deleting}
        onConfirm={handleDelete}
        onClose={() => setConfirmTarget(null)}
      />
    </div>
  )
}
