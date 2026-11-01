import { useMemo, useState } from 'react'
import './CoinBudgetPanel.css'

const number = value => Number(value || 0).toLocaleString('ru-RU')
const months = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr']
const teacherKey = group => String(group.teacher_id ?? 'unassigned')

export default function CoinBudgetPanel({ groups, loading, isTeacher, onGive, onRefresh }) {
  const [teacher, setTeacher] = useState('all')
  const [search, setSearch] = useState('')
  const teachers = useMemo(() => [...new Map(groups.map(g => [teacherKey(g), g])).values()], [groups])
  const selected = groups.filter(g => teacher === 'all' || teacherKey(g) === teacher)
  const visible = selected.filter(g => `${g.name} ${g.teacher_name}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  const students = [...new Map(selected.flatMap(g => g.students).map(s => [s.id, s])).values()]
  const used = students.reduce((sum, s) => sum + s.used, 0)
  const available = students.reduce((sum, s) => sum + s.remaining, 0)
  const period = groups[0] && `${months[groups[0].month - 1]} ${groups[0].year}`

  return <section className="coin-planner" aria-label="Guruhlarning oylik coin limitlari" aria-busy={loading}>
    <div className="coin-planner-hero">
      <div><span className="coin-eyebrow">MINAR ACADEMY · {period || 'OYLIK LIMIT'}</span>
        <h2>Mehnatga yarasha rag‘bat.</h2>
        <p>Har bir o‘quvchi uchun oyiga <strong>70 coin</strong>. Guruh va ustoz limitlari faol o‘quvchilar soniga qarab avtomatik hisoblanadi.</p>
        <div className="coin-rule-pills"><span>Davomat · +1</span><span>Vazifa va test · ustoz bahosi</span><span>O‘yinlar · 0 coin</span></div>
      </div>
      <img src="/brand/minar-gold-coin.webp" alt="Minar Academy oltin coini" width="132" height="140" />
    </div>
    <div className="coin-planner-stats">
      <div><span>Faol o‘quvchilar</span><strong>{number(students.length)}</strong><small>{selected.length} ta guruhda</small></div>
      <div><span>Oylik umumiy limit</span><strong>{number(students.length * 70)} <small>coin</small></strong><small>Takroriy o‘quvchi bir marta sanaladi</small></div>
      <div><span>O‘quvchilarga berilgan</span><strong>{number(used)} <small>coin</small></strong><small>Joriy kalendar oy uchun</small></div>
      <div><span>O‘quvchilar qoldig‘i</span><strong>{number(available)} <small>coin</small></strong><small>Barcha guruhlari bo‘yicha jami</small></div>
    </div>
    {!isTeacher && <div className="coin-teachers" aria-label="O‘qituvchi bo‘yicha filtr">
      <button type="button" className={teacher === 'all' ? 'is-selected' : ''} onClick={() => setTeacher('all')} aria-pressed={teacher === 'all'}><strong>Barcha o‘qituvchilar</strong><span>{teachers.filter(t => t.teacher_id).length} ustoz · {groups.length} guruh</span></button>
      {teachers.map(t => <button type="button" key={teacherKey(t)} className={teacher === teacherKey(t) ? 'is-selected' : ''} onClick={() => setTeacher(teacherKey(t))} aria-pressed={teacher === teacherKey(t)}>
        <strong>{t.teacher_name}</strong><span>{number(t.teacher_budget)} coin / oy · {t.teacher_students} o‘quvchi</span>
      </button>)}
    </div>}
    {(isTeacher || teacher !== 'all') && selected[0]?.teacher_id && <div className="coin-teacher-summary">
      <strong>{selected[0].teacher_name}</strong><span>Ustoz limiti: {number(selected[0].teacher_budget)} · Ustoz bergan: {number(selected[0].teacher_used)} · Hozir berishi mumkin: <b>{number(selected[0].teacher_available)} coin</b></span>
    </div>}
    <div className="coin-planner-toolbar"><div><h3>Guruhlar taqsimoti</h3><p>70 coin — barcha guruhlar uchun bitta o‘quvchi limiti.</p></div>
      <div><input className="field" aria-label="Coin guruhini qidirish" placeholder="Guruhni qidirish…" value={search} onChange={e => setSearch(e.target.value)} />
        <button className="button secondary" onClick={onRefresh} disabled={loading}>{loading ? 'Yuklanmoqda…' : 'Yangilash'}</button></div>
    </div>
    {visible.length === 0 && <div className="coin-empty">{loading ? 'Limitlar yuklanmoqda…' : 'Bu tanlovda faol guruh topilmadi.'}</div>}
    <div className="coin-group-grid">{visible.map(g => <details key={g.id} className="coin-group-card">
      <summary><div className="coin-group-heading"><div><span className="coin-group-kicker">{g.teacher_name}</span><h4>{g.name}</h4></div><span className="coin-group-expand" aria-hidden="true">⌄</span></div>
        <div className="coin-group-amount"><strong>{number(g.budget)}</strong><span>coin / oy</span><small>{g.students.length} o‘quvchi × 70</small></div>
        <div className="coin-budget-track" role="progressbar" aria-label={`${g.name}: berilgan coin`} aria-valuenow={Math.min(g.used, g.budget)} aria-valuemin={0} aria-valuemax={g.budget || 1}><span style={{ width: `${Math.min(100, g.budget ? g.used / g.budget * 100 : 0)}%` }} /></div>
        <div className="coin-group-remaining"><span>Berilgan <b>{number(g.used)}</b></span><span>Hozir berish mumkin <b>{number(g.available)}</b></span></div>
      </summary>
      <div className="coin-group-students">
        {g.students.length === 0 && <p className="text-muted">Faol o‘quvchi qo‘shilganda limit avtomatik ajratiladi.</p>}
        {g.students.map(s => <div key={s.id} className="coin-student-row"><div><strong>{s.name}</strong><small>{s.used} / 70 berilgan · {s.remaining} qoldiq</small></div>
          <button type="button" className="button secondary" disabled={s.remaining === 0 || g.available === 0} onClick={() => onGive(g.id, s.id)} aria-label={`${s.name} uchun coin berish`}>{s.remaining === 0 ? 'Limit tugagan' : '+ Coin'}</button></div>)}
      </div>
    </details>)}</div>
    <p className="coin-budget-note">Limit har oyning 1-sanasida yangilanadi. Coin sarflash yoki berilgan coinni bekor qilish oylik limitni qayta to‘ldirmaydi. Bir o‘quvchiga boshqa guruhda berilgan coin ham uning 70 coinlik limitiga kiradi.</p>
  </section>
}
