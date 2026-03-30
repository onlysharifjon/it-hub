function ProgressBar({ value }) {
  return (
    <div className="progress" aria-label="Bajarilish" role="progressbar">
      <div className="progress-bar" style={{ width: `${value}%` }} />
    </div>
  )
}

export default ProgressBar

