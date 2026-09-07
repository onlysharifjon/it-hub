import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faStar, faPlus, faTrash, faToggleOn, faToggleOff } from '@fortawesome/free-solid-svg-icons'
import {
  fetchSpecialDiscounts, createSpecialDiscount, updateSpecialDiscount, deleteSpecialDiscount,
  fetchStudents, fetchGroups,
} from '../api'
import DataTable, { RowActions } from './ui/DataTable'
import Modal from './ui/Modal'
import ConfirmDialog from './ui/ConfirmDialog'
import Badge from './ui/Badge'
import { Input, Select } from './ui/Field'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)
const EMPTY = {
  student_id: '', group_id: '', kind: 'one_time',
  amount: '', month: NOW.getMonth() + 1, year: NOW.getFullYear(), reason: '',
}

export default function Special() {
  const [items, setItems] = useState([])
  const [students, setStudents] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  useEffect(() => {
    load()
    fetchStudents({ page_size: 100 }).then(r => setStudents(r.items || []))
    fetchGroups({ page_size: 100 }).then(r => setGroups(r.items || []))
  }, [])

  async function load() {
    setLoading(true)
    try { setItems(await fetchSpecialDiscounts()) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleSave() {
    if (!form.student_id) return toast.error("Talabani tanlang")
    if ((form.kind === 'monthly' || form.kind === 'one_time') && (!form.amount || parseFloat(form.amount) <= 0)) {
      return toast.error("Chegirma summasini kiriting")
    }
    setSaving(true)
    try {
      await createSpecialDiscount({
        student_id: parseInt(form.student_id),
        group_id: form.group_id ? parseInt(form.group_id) : null,
        kind: form.kind,
        amount: (form.kind === 'monthly' || form.kind === 'one_time') ? parseFloat(form.amount) : null,
        month: (form.kind === 'free_month' || form.kind === 'one_time') ? parseInt(form.month) : null,
        year: (form.kind === 'free_month' || form.kind === 'one_time') ? parseInt(form.year) : null,
        reason: form.reason || null,
      })
      toast.success("Chegirma berildi")
      setModal(false)
      setForm(EMPTY)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(d) {
    try {
      await updateSpecialDiscount(d.id, { is_active: !d.is_active })
      toast.success(d.is_active ? "Chegirma to'xtatildi" : "Chegirma yoqildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleDelete() {
    try {
      await deleteSpecialDiscount(deleteTarget.id)
      toast.success("O'chirildi")
      setDeleteTarget(null)
      load()
    } catch (e) { toast.error(e.message) }
  }

  function kindLabel(d) {
    if (d.kind === 'free_month') {
      return `${MONTHS[(d.month || 1) - 1]} ${d.year} — to'liq bepul`
    }
    if (d.kind === 'one_time') {
      return `${MONTHS[(d.month || 1) - 1]} ${d.year} — bir martalik ${Number(d.amount).toLocaleString()} so'm`
    }
    return `Har oy ${Number(d.amount).toLocaleString()} so'm (butun kurs)`
  }

  const KIND_VARIANT = { free_month: 'success', one_time: 'warning', monthly: 'primary' }

  const columns = [
    { key: 'student_name', header: 'Talaba', sortable: true, render: d => <strong>{d.student_name}</strong> },
    {
      key: 'group_name', header: 'Guruh', sortable: true,
      render: d => d.group_name || <span className="text-muted">Barcha guruhlar</span>,
    },
    {
      key: 'kind', header: 'Chegirma', sortable: true,
      render: d => <Badge variant={KIND_VARIANT[d.kind] || 'neutral'} size="sm">{kindLabel(d)}</Badge>,
    },
    { key: 'reason', header: 'Sabab', render: d => d.reason || <span className="text-muted">—</span> },
    { key: 'created_by_name', header: 'Kim berdi', sortable: true, render: d => <span className="text-muted">{d.created_by_name || '—'}</span> },
    {
      key: 'is_active', header: 'Holat', sortable: true,
      render: d => (
        <span className={`status-badge ${d.is_active ? 'active' : 'inactive'}`}>
          {d.is_active ? 'Faol' : "To'xtatilgan"}
        </span>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: d => (
        <RowActions>
          <button className="btn-icon" title={d.is_active ? "To'xtatish" : 'Yoqish'}
            aria-label={d.is_active ? "To'xtatish" : 'Yoqish'} onClick={() => handleToggle(d)}>
            <FontAwesomeIcon icon={d.is_active ? faToggleOn : faToggleOff} />
          </button>
          <button className="btn-icon danger" title="O'chirish" aria-label="O'chirish" onClick={() => setDeleteTarget(d)}>
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </RowActions>
      ),
    },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faStar} className="page-icon" /> Special chegirmalar</h1>
          <p className="page-subtitle">
            To'lov hisobiga bevosita ta'sir qiladi — qarzdorlik, Moliya va ota-ona ilovasida ham.
          </p>
        </div>
        <div className="header-actions">
          <button className="button" onClick={() => { setForm(EMPTY); setModal(true) }}>
            <FontAwesomeIcon icon={faPlus} /> Chegirma berish
          </button>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        rowClassName={d => (!d.is_active ? 'row-inactive' : undefined)}
        clientPageSize={25}
        empty={{
          icon: faStar,
          title: "Chegirmalar yo'q",
          description: 'Alohida talabaga individual chegirma berish uchun tugmani bosing.',
          action: (
            <button className="button" onClick={() => { setForm(EMPTY); setModal(true) }}>
              <FontAwesomeIcon icon={faPlus} /> Chegirma berish
            </button>
          ),
        }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="Chegirmani o'chirish"
        message={deleteTarget ? `${deleteTarget.student_name} uchun chegirma o'chiriladi.` : ''}
        detail="Chegirma o'chirilgach, keyingi hisob-kitoblarda hisobga olinmaydi."
        confirmLabel="Ha, o'chirish"
        onConfirm={handleDelete}
        onClose={() => setDeleteTarget(null)}
      />

      <Modal
        open={modal}
        title="Special chegirma"
        onClose={() => setModal(false)}
        footer={
          <>
            <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
            <button className="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Select label="Talaba" required value={form.student_id}
          onChange={e => setForm(p => ({ ...p, student_id: e.target.value }))}>
          <option value="">— Tanlang —</option>
          {students.map(s => <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>)}
        </Select>

        <Select label="Guruh" hint="Bo'sh qoldirilsa — talabaning barcha guruhlariga tegishli"
          value={form.group_id} onChange={e => setForm(p => ({ ...p, group_id: e.target.value }))}>
          <option value="">Barcha guruhlar</option>
          {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
        </Select>

        <Select label="Chegirma turi" required value={form.kind}
          onChange={e => setForm(p => ({ ...p, kind: e.target.value }))}>
          <option value="one_time">Bir martalik summa (bitta oy uchun)</option>
          <option value="monthly">Oylik summa (butun kurs davomida)</option>
          <option value="free_month">To'liq 1 oylik (tanlangan oy bepul)</option>
        </Select>

        {(form.kind === 'free_month' || form.kind === 'one_time') && (
          <div className="field-row">
            <Select label="Oy" required value={form.month}
              onChange={e => setForm(p => ({ ...p, month: e.target.value }))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </Select>
            <Select label="Yil" required value={form.year}
              onChange={e => setForm(p => ({ ...p, year: e.target.value }))}>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </Select>
          </div>
        )}

        {form.kind === 'monthly' && (
          <Input
            label="Oylik chegirma summasi (so'm)" required
            type="text" inputMode="numeric" value={form.amount}
            onChange={e => setForm(p => ({ ...p, amount: e.target.value.replace(/\D/g, '') }))}
            placeholder="100000"
            hint="Har oy to'lovdan shu summa ayiriladi — chegirma to'xtatilguncha."
          />
        )}

        {form.kind === 'one_time' && (
          <Input
            label="Chegirma summasi (so'm)" required
            type="text" inputMode="numeric" value={form.amount}
            onChange={e => setForm(p => ({ ...p, amount: e.target.value.replace(/\D/g, '') }))}
            placeholder="100000"
            hint="Faqat tanlangan oy uchun shu summa bir marta ayiriladi."
          />
        )}

        <Input label="Sabab / izoh" value={form.reason}
          onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} placeholder="Ixtiyoriy" />
      </Modal>

    </div>
  )
}
