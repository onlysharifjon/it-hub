import { useEffect, useState } from 'react';
import { spaceStaff as api } from '../api';
import './SpaceAcademy.css';
const date = d => new Date(d).toLocaleString('uz-UZ');
function useLoad(path) {
  const [data, setData] = useState(null),
    [error, setError] = useState('');
  const load = async () => {
    try {
      setData(await api.get(path));
      setError('');
    } catch (e) {
      setError(e.message);
    }
  };
  useEffect(() => {
    let active = true;
    setData(null);
    api.get(path).then(d => active && setData(d)).catch(e => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [path]);
  return {
    data,
    error,
    load,
    setError
  };
}
function ErrorBox({
  text
}) {
  return text ? <p role="alert" className="sa-error">{text}</p> : null;
}
function Loading({
  error,
  load
}) {
  return <div className="sa-card" role="status">{error || 'Yuklanmoqda…'}{error && <button className="btn btn-secondary" onClick={load}>Qayta urinish</button>}</div>;
}
function Text({
  text = ''
}) {
  return <div className="sa-reading">{text.split(/```/).map((b, i) => i % 2 ? <pre key={i}>{b}</pre> : b.split('\n').map((line, j) => line.startsWith('#') ? <h3 key={j}>{line.replace(/^#+\s*/, '')}</h3> : line.startsWith(':: timer') ? null : line.startsWith('!! ') ? <blockquote key={j}>{line.slice(3)}</blockquote> : <p key={j}>{line.split(/(\*\*.*?\*\*|`[^`]+`)/).map((x, k) => x.startsWith('**') ? <strong key={k}>{x.slice(2, -2)}</strong> : x.startsWith('`') ? <code key={k}>{x.slice(1, -1)}</code> : x)}</p>))}</div>;
}
function Slides({
  data,
  onClose
}) {
  const slides = (data.slides || `# ${data.title}\n---\n${data.body}\n---\n## Mustaqil mashq\n${data.exercise || ''}`).split(/\n---\n/),
    [index, setIndex] = useState(0),
    [seconds, setSeconds] = useState(0),
    [running, setRunning] = useState(false);
  useEffect(() => {
    setRunning(false);
    const n = slides[index].match(/:: timer (\d+)/);
    setSeconds(n ? Number(n[1]) * 60 : 0);
  }, [index]);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setSeconds(s => {
      if (s <= 1) setRunning(false);
      return Math.max(0, s - 1);
    }), 1000);
    return () => clearInterval(timer);
  }, [running]);
  useEffect(() => {
    const key = e => {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        setIndex(i => Math.min(slides.length - 1, i + 1));
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setIndex(i => Math.max(0, i - 1));
      }
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [slides.length, onClose]);
  return <section className="sa-slides"><header><span>MINAR SPACE • DARS</span><button className="btn btn-secondary" onClick={onClose}>Yopish (Esc)</button></header><article key={index}><Text text={slides[index]} /></article>{/:: timer/.test(slides[index]) && <div className="sa-timer"><strong>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</strong><button className="btn btn-primary" disabled={!seconds} onClick={() => setRunning(!running)}>{running ? 'Pauza' : 'Taymerni boshlash'}</button><button className="btn btn-secondary" onClick={() => {
        setRunning(false);
        setSeconds(Number(slides[index].match(/:: timer (\d+)/)[1]) * 60);
      }}>Qayta</button></div>}<footer><button className="btn btn-secondary" disabled={!index} onClick={() => setIndex(index - 1)}>← Oldingi</button><span>{index + 1} / {slides.length}</span><button className="btn btn-primary" disabled={index === slides.length - 1} onClick={() => setIndex(index + 1)}>Keyingi →</button></footer></section>;
}
function Editor({
  id,
  onBack,
  teacher
}) {
  const {
      data,
      error,
      load
    } = useLoad('/academy/topics/' + id),
    [form, setForm] = useState(null),
    [published, setPublished] = useState(false),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false),
    [slide, setSlide] = useState(false),
    [lang, setLang] = useState('uz');
  useEffect(() => {
    if (data) {
      setForm(data.data);
      setPublished(data.published);
    }
  }, [data]);
  if (!form) return <Loading error={error} load={load} />;
  if (slide) return <Slides data={form} onClose={() => setSlide(false)} />;
  const set = (k, v) => setForm({
    ...form,
    [k]: v
  });
  const key = k => lang === 'ru' ? k + '_ru' : k;
  const question = (i, k, v) => set('questions', form.questions.map((q, j) => i === j ? {
    ...q,
    [k]: v
  } : q));
  return <form className="sa-card sa-form" onSubmit={async e => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.save('/academy/topics/' + id, {
        data: form,
        published
      });
      setMessage('Saqlandi. Oldingi test natijalari o‘zgarmaydi.');
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  }}><div className="sa-row"><button type="button" className="btn btn-secondary" onClick={onBack}>← Kutubxona</button><button type="button" className="btn btn-secondary" onClick={() => setSlide(true)}>Dars slaydlari</button></div><div className="sa-row"><h2>{data.title}</h2><label>Kontent tili<select value={lang} onChange={e => setLang(e.target.value)}><option value="uz">O‘zbekcha</option><option value="ru">Русский</option></select></label></div><fieldset disabled={teacher || busy} className="sa-fields"><label>Sarlavha<input value={form[key('title')] || ''} maxLength={250} required={lang === 'uz'} onChange={e => set(key('title'), e.target.value)} /></label><label>Dars materiali<textarea className="sa-long" required={lang === 'uz'} maxLength={60000} value={form[key('body')] || ''} onChange={e => set(key('body'), e.target.value)} /></label><label>Mustaqil mashq<textarea maxLength={10000} value={form.exercise || ''} onChange={e => set('exercise', e.target.value)} /></label><details><summary>Slayd matnlari va manbalar</summary><label>Slaydlar (ajratish: alohida qatorda ---; taymer: :: timer 25)<textarea className="sa-long" maxLength={60000} value={form.slides || ''} onChange={e => set('slides', e.target.value)} /></label><label>Manbalar<textarea value={form.resources || ''} maxLength={10000} onChange={e => set('resources', e.target.value)} /></label></details><h3>Savollar banki · {form.questions.length}</h3>{form.questions.map((q, i) => <details className="sa-question" key={q.id}><summary>{i + 1}. {q[key('q')] || q.q}</summary><label>Savol<textarea required maxLength={5000} value={q[key('q')] || ''} onChange={e => question(i, key('q'), e.target.value)} /></label>{q.options.map((_, j) => <label className="sa-option" key={j}><input type="radio" name={'answer-' + q.id} checked={q.answer === j} onChange={() => question(i, 'answer', j)} /><input aria-label={`Variant ${j + 1}`} required value={(q[key('options')] || [])[j] || ''} maxLength={2000} onChange={e => {
            const opts = [...(q[key('options')] || q.options.map(() => ''))];
            opts[j] = e.target.value;
            question(i, key('options'), opts);
          }} /></label>)}<label>Rasm havolasi (ixtiyoriy)<input type="url" maxLength={2000} value={q.image || ''} onChange={e => question(i, 'image', e.target.value)} /></label><button type="button" className="btn btn-secondary" disabled={form.questions.length <= 1} onClick={() => set('questions', form.questions.filter((_, j) => j !== i))}>Savolni olib tashlash</button></details>)}<button type="button" className="btn btn-secondary" disabled={form.questions.length >= 200} onClick={() => set('questions', [...form.questions, {
        id: crypto.randomUUID(),
        q: '',
        q_ru: '',
        options: ['', '', '', ''],
        options_ru: [],
        answer: 0
      }])}>+ Savol qo‘shish</button><label className="sa-check"><input type="checkbox" checked={published} onChange={e => setPublished(e.target.checked)} />Nashr qilingan — guruhga test berish mumkin</label></fieldset>{message && <p role="status">{message}</p>}{!teacher && <button className="btn btn-primary" disabled={busy}>{busy ? 'Saqlanmoqda…' : 'O‘zgarishlarni saqlash'}</button>}</form>;
}
function Library({
  teacher
}) {
  const {
      data,
      error,
      load
    } = useLoad('/academy/library'),
    [selected, setSelected] = useState([]),
    [query, setQuery] = useState(''),
    [course, setCourse] = useState(''),
    [edit, setEdit] = useState(null),
    [preview, setPreview] = useState(null),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false),
    [newTitle, setNewTitle] = useState('');
  if (edit) return <Editor id={edit} teacher={teacher} onBack={() => {
    setEdit(null);
    load();
  }} />;
  const filtered = data?.filter(x => (!course || x.course === course) && x.title.toLowerCase().includes(query.toLowerCase())) || [];
  const previewItem = async x => {
    setBusy(true);
    try {
      setPreview(await api.get('/academy/library/' + x.slug));
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  return <><div className="sa-card"><div className="sa-heading"><div><h2>O‘quv kutubxonasi</h2><p>Materiallarni ko‘rib chiqing, import qiling va tayyor bo‘lgach nashr qiling.</p></div><span className="sa-badge">77 mavzu · 924 savol</span></div><div className="sa-row"><input aria-label="Mavzu qidirish" placeholder="Mavzuni qidirish…" value={query} onChange={e => setQuery(e.target.value)} /><select aria-label="Kurs" value={course} onChange={e => setCourse(e.target.value)}><option value="">Barcha kurslar</option>{[...new Set(data?.map(x => x.course))].map(c => <option key={c}>{c}</option>)}</select>{!teacher && <><button className="btn btn-secondary" onClick={() => setSelected(filtered.filter(x => !x.id).map(x => x.slug))}>Ko‘rsatilganlarni belgilash</button><button className="btn btn-primary" disabled={busy || !selected.length} onClick={async () => {
            setBusy(true);
            try {
              const r = await api.save('/academy/import', {
                slugs: selected
              });
              setMessage(`${r.added} ta mavzu import qilindi, ${r.skipped} tasi avval mavjud.`);
              setSelected([]);
              load();
            } catch (e) {
              setMessage(e.message);
            } finally {
              setBusy(false);
            }
          }}>Import ({selected.length})</button></>}</div>{!teacher && <form className="sa-row sa-new" onSubmit={async e => {
        e.preventDefault();
        setBusy(true);
        try {
          const r = await api.save('/academy/topics', {
            title: newTitle,
            course: course || 'Foundation'
          });
          setEdit(r.id);
        } catch (e) {
          setMessage(e.message);
        } finally {
          setBusy(false);
        }
      }}><input aria-label="Yangi mavzu nomi" value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="Yangi mavzu nomi" required maxLength={250} /><button className="btn btn-secondary" disabled={busy}>+ Yangi mavzu</button></form>}{message && <p role="status" className="sa-message">{message}</p>}</div>{preview && <section className="sa-card sa-preview"><div className="sa-row"><h2>{preview.title}</h2><button className="btn btn-secondary" onClick={() => setPreview(null)}>Yopish</button></div><Text text={preview.body} /><h3>Savol namunasi</h3><Text text={preview.questions[0]?.q} /></section>}{!data ? <Loading error={error} load={load} /> : <div className="sa-library-grid">{filtered.map(x => <article className="sa-card" key={x.slug}><div className="sa-row"><span className="sa-kicker">{x.course}</span>{!teacher && !x.id && <input type="checkbox" aria-label={x.title + ' ni belgilash'} checked={selected.includes(x.slug)} onChange={e => setSelected(e.target.checked ? [...selected, x.slug] : selected.filter(s => s !== x.slug))} />}<span className="sa-badge">{x.id ? x.published ? 'Nashr qilingan' : 'Qoralama' : 'Import qilinmagan'}</span></div><h3>{x.title}</h3><p>{x.questionCount} savol · {x.hasRussian ? 'UZ / RU' : 'UZ'}{x.hasSlides ? ' · Slaydlar' : ''}</p><button disabled={busy} className="btn btn-secondary" onClick={() => x.id ? setEdit(x.id) : previewItem(x)}>{x.id ? 'Ochish va tahrirlash' : 'Oldindan ko‘rish'}</button></article>)}</div>}</>;
}
function Assignments() {
  const list = useLoad('/academy/assignments'),
    library = useLoad('/academy/library'),
    groups = useLoad('/academy/groups');
  const [form, setForm] = useState({
      topicId: '',
      groupId: '',
      count: 10,
      minutes: 15,
      maxAttempts: 2,
      startsAt: '',
      dueAt: '',
      public: false,
      title: ''
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [link, setLink] = useState('');
  const set = (k, v) => setForm({
    ...form,
    [k]: v
  });
  const url = token => `${import.meta.env.VITE_SPACE_URL || 'https://space.minaracademy.uz'}/?entry=${encodeURIComponent(token)}`;
  return <><form className="sa-card sa-form" onSubmit={async e => {
      e.preventDefault();
      setBusy(true);
      try {
        const payload = {
          ...form,
          topicId: Number(form.topicId),
          groupId: Number(form.groupId),
          startsAt: form.startsAt ? new Date(form.startsAt).toISOString() : null,
          dueAt: new Date(form.dueAt).toISOString()
        };
        const r = await api.save('/academy/assignments', payload);
        setLink(r.publicToken ? url(r.publicToken) : '');
        setError('');
        list.load();
      } catch (e) {
        setError(e.message);
      } finally {
        setBusy(false);
      }
    }}><div className="sa-heading"><div><h2>Yangi test</h2><p>Guruhga topshiriq bering yoki kirish testi uchun ochiq havola yarating.</p></div></div><div className="sa-grid"><label>Mavzu<select required value={form.topicId} onChange={e => set('topicId', e.target.value)}><option value="">Nashr qilingan mavzuni tanlang</option>{library.data?.filter(t => t.published).map(t => <option key={t.id} value={t.id}>{t.course} · {t.title}</option>)}</select></label><label>Test nomi (ixtiyoriy)<input maxLength={250} value={form.title} onChange={e => set('title', e.target.value)} /></label><label>Test turi<select value={form.public ? 'public' : 'group'} onChange={e => set('public', e.target.value === 'public')}><option value="group">Guruh testi</option><option value="public">Ochiq kirish testi</option></select></label>{!form.public && <label>Guruh<select required value={form.groupId} onChange={e => set('groupId', e.target.value)}><option value="">Guruhni tanlang</option>{groups.data?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>}{[['count', 'Savollar soni', 1, 100], ['minutes', 'Vaqt (daqiqa)', 1, 180], ['maxAttempts', 'Urinishlar soni', 1, 5]].map(([k, label, min, max]) => <label key={k}>{label}<input type="number" min={min} max={max} required value={form[k]} onChange={e => set(k, Number(e.target.value))} /></label>)}<label>Boshlanish (bo‘sh — hozir)<input type="datetime-local" value={form.startsAt} onChange={e => set('startsAt', e.target.value)} /></label><label>Yakuniy muddat<input type="datetime-local" required value={form.dueAt} onChange={e => set('dueAt', e.target.value)} /></label></div><p className="sa-muted">Vaqt brauzeringiz mintaqasida. Rejalashtirilgan test boshlanishida bildirishnoma beriladi; 3 soatdan keyin bajarilmagan test uchun eslatma chiqadi.</p><ErrorBox text={error || library.error || groups.error} /><button className="btn btn-primary" disabled={busy}>{busy ? 'Yaratilmoqda…' : 'Testni yaratish'}</button>{link && <label>Ulashish havolasi<input readOnly value={link} onFocus={e => e.target.select()} /></label>}</form>{!list.data ? <Loading error={list.error} load={list.load} /> : <div className="sa-card"><h2>Berilgan testlar</h2>{!list.data.length && <p>Hozircha testlar yo‘q.</p>}<div className="sa-table-wrap"><table className="sa-table"><thead><tr><th>Test</th><th>Format</th><th>Muddat</th><th>Holat</th><th>Amal</th></tr></thead><tbody>{list.data.map(a => <tr key={a.id}><td><strong>{a.title}</strong><small>{a.count} savol · {a.minutes} daqiqa</small>{a.publicToken && <a href={url(a.publicToken)} target="_blank" rel="noreferrer">Kirish testi havolasi ↗</a>}</td><td>{a.publicToken ? 'Ochiq test' : groups.data?.find(g => g.id === a.groupId)?.name || 'Guruh'}</td><td>{date(a.dueAt)}</td><td>{a.active ? 'Faol' : 'Yopilgan'}</td><td><button className="btn btn-secondary" disabled={busy} onClick={async () => {
                  setBusy(true);
                  try {
                    await api.save(`/academy/assignments/${a.id}/status`, {
                      active: !a.active
                    });
                    list.load();
                  } catch (e) {
                    setError(e.message);
                  } finally {
                    setBusy(false);
                  }
                }}>{a.active ? 'Yopish' : 'Yoqish'}</button></td></tr>)}</tbody></table></div></div>}</>;
}
function Analytics({
  teacher
}) {
  const [aid, setAid] = useState(''),
    list = useLoad('/academy/assignments'),
    {
      data,
      error,
      load
    } = useLoad('/academy/report' + (aid ? '?assignmentId=' + aid : '')),
    [selected, setSelected] = useState(null),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false);
  const exportCSV = () => {
    const cell = x => '"' + String(x ?? '').replace(/^[=+@-]/, "'$&").replaceAll('"', '""') + '"';
    const rows = [['O‘quvchi', 'Natija %', 'Yakunlangan', 'Oynadan chiqish'], ...data.attempts.map(a => [a.student, a.score, a.finishedAt || '', a.warnings])];
    const blob = new Blob(['\ufeff' + rows.map(r => r.map(cell).join(',')).join('\r\n')], {
      type: 'text/csv;charset=utf-8'
    });
    const url = URL.createObjectURL(blob),
      a = document.createElement('a');
    a.href = url;
    a.download = 'space-test-natijalari.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <><div className="sa-row"><label>Test bo‘yicha filtr<select value={aid} onChange={e => {
          setAid(e.target.value);
          setSelected(null);
        }}><option value="">Barcha testlar</option>{list.data?.map(a => <option key={a.id} value={a.id}>{a.title}</option>)}</select></label><button className="btn btn-secondary" onClick={load}>Yangilash</button>{data && <button className="btn btn-secondary" onClick={exportCSV}>CSV eksport</button>}</div>{!data ? <Loading error={error} load={load} /> : <><div className="sa-metrics">{[['Bugun yakunlangan', data.daily.completed], ['O‘rtacha natija', data.daily.average === null ? '—' : data.daily.average + '%'], ['50% dan past', data.daily.below50], ['Yordam kerak', data.atRisk.length]].map(([label, v]) => <div className="sa-card" key={label}><span>{label}</span><strong>{v}</strong></div>)}</div><section className="sa-card"><h2>E’tibor talab qiladigan o‘quvchilar</h2>{data.atRisk.length ? data.atRisk.map(s => <div key={s.accountId} className="sa-risk"><strong>{s.student}</strong><span>{s.average}% · {s.reason}</span></div>) : <p className="sa-muted">Past natijali o‘quvchilar hozircha qayd etilmagan.</p>}</section><section className="sa-card"><h2>Natijalar va javoblar</h2><p className="sa-muted">{data.total} ta urinish. Tahlilda oxirgi {data.analysisLimit} tagacha urinish ko‘rsatiladi. Kunlik ko‘rsatkichlar bugungi barcha natijalarni qamraydi.</p><ErrorBox text={message} /><div className="sa-table-wrap"><table className="sa-table"><thead><tr><th>O‘quvchi</th><th>Natija</th><th>Yakunlangan</th><th>Qaydlar</th><th>Amal</th></tr></thead><tbody>{data.attempts.map(a => <tr key={a.id}><td>{a.student}{a.phone && <small>{a.phone}</small>}</td><td>{a.score === null ? 'Jarayonda' : a.score + '%'}</td><td>{a.finishedAt ? date(a.finishedAt) : '—'}</td><td>{a.warnings ? `${a.warnings} marta oynadan chiqqan` : '—'}</td><td><button className="btn btn-secondary" onClick={async () => {
                    setBusy(true);
                    try {
                      setSelected(await api.get('/academy/attempts/' + a.id));
                    } catch (e) {
                      setMessage(e.message);
                    } finally {
                      setBusy(false);
                    }
                  }} disabled={busy}>Javoblar</button>{!teacher && !a.accountId && a.finishedAt && <button className="btn btn-secondary" disabled={busy || a.leadId} onClick={async () => {
                    setBusy(true);
                    try {
                      const r = await api.save('/academy/attempts/' + a.id + '/lead', {});
                      setMessage('CRM arizasiga bog‘landi: #' + r.leadId);
                      load();
                    } catch (e) {
                      setMessage(e.message);
                    } finally {
                      setBusy(false);
                    }
                  }}>{a.leadId ? 'CRM’da mavjud' : 'CRM arizasiga olish'}</button>}</td></tr>)}</tbody></table></div><p className="sa-muted">Oynadan chiqish qaydi ko‘chirishni isbotlamaydi. Natijani suhbat va amaliy ish bilan birga baholang.</p></section>{selected && <section className="sa-card"><div className="sa-row"><h2>{selected.student} · javoblar</h2><button className="btn btn-secondary" onClick={() => setSelected(null)}>Yopish</button></div>{selected.questions.map((q, i) => <div className="sa-answer" key={q.id}><strong>{i + 1}. {q.q}</strong><p>Tanlagan: {q.options[selected.answers[q.id]] || 'Javobsiz'}</p>{selected.review && <p className={selected.review[i].correct ? 'sa-success' : 'sa-danger'}>To‘g‘ri javob: {q.options[selected.review[i].answer]}</p>}</div>)}</section>}<section className="sa-card"><h2>Savollar sifati</h2><p className="sa-muted">Kamida 5 javobdan keyin: 30% dan past — qiyin; 95% va undan yuqori — oson.</p>{data.questions.map(q => <div className="sa-answer" key={q.id}><div className="sa-row"><strong>{q.q}</strong><span className="sa-badge">{q.percent}% · {q.total} javob{q.quality === 'normal' ? '' : ' · ' + q.quality}</span></div><div className="sa-bar"><i style={{
              width: q.percent + '%'
            }} /></div>{Object.keys(q.wrongOptions).length > 0 && <p>Ko‘p tanlangan xato: {Object.entries(q.wrongOptions).sort((a, b) => b[1] - a[1])[0].join(' — ')}</p>}</div>)}</section></>}</>;
}
export default function SpaceAcademy({
  teacher = false
}) {
  const [tab, setTab] = useState('library');
  return <div className="sa-workspace"><nav className="sa-tabs" aria-label="Test boshqaruvi">{[['library', 'Kutubxona va savollar'], ['assignments', 'Test berish'], ['analytics', 'Natijalar va tahlil']].map(([id, label]) => <button className={tab === id ? 'active' : ''} aria-pressed={tab === id} key={id} onClick={() => setTab(id)}>{label}</button>)}</nav>{tab === 'library' ? <Library teacher={teacher} /> : tab === 'assignments' ? <Assignments /> : <Analytics teacher={teacher} />}</div>;
}
