export default function PersonName({ name, sub }) {
  const text = name || '—'
  const initials = text.split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase()
  const tone = [...text].reduce((n, c) => n + c.charCodeAt(0), 0) % 4
  return <span className="person-name"><span className={`person-initials person-tone-${tone}`} aria-hidden="true">{initials}</span><span className="person-name-copy"><strong>{text}</strong>{sub && <small>{sub}</small>}</span></span>
}
