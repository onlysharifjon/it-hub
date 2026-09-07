/**
 * Bo'lim sarlavhasi — sarlavha + izoh + o'ng tomonda amallar.
 *
 * Nima uchun: sahifalarda bo'lim sarlavhalari uch xil usulda yozilgan edi
 * (`<h2 className="dash-section-title">`, `.chart-card-head > h2`, va shunchaki
 * inline-styled `div`). Vertikal ritm har joyda boshqacha bo'lib, sahifa
 * "yig'ilgan" emas, "tashlangan" ko'rinardi.
 */
export default function SectionHead({ title, description, actions, id }) {
  return (
    <div className="ui-section-head">
      <div className="ui-section-head-text">
        <h2 id={id}>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="ui-section-head-actions">{actions}</div>}
    </div>
  )
}
