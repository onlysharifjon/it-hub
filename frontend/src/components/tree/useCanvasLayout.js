import { useEffect, useReducer, useState } from 'react'
import { layoutHistory, validPositions } from './canvasGeometry'

function read(key) {
  try { return validPositions(JSON.parse(localStorage.getItem(key) || '{}')) } catch { return {} }
}

export default function useCanvasLayout(key) {
  const [history, dispatch] = useReducer(layoutHistory, key, value => ({ entries: [read(value)], index: 0 }))
  const [saved, setSaved] = useState(true)
  useEffect(() => { dispatch({ type: 'load', positions: read(key) }) }, [key])
  const positions = history.entries[history.index]
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(positions)); setSaved(true) }
    catch { setSaved(false) }
  }, [key, positions])
  return { positions, saved, move: (key, position) => dispatch({ type: 'move', key, position }), reset: () => dispatch({ type: 'reset' }), undo: () => dispatch({ type: 'undo' }), redo: () => dispatch({ type: 'redo' }), canUndo: history.index > 0, canRedo: history.index < history.entries.length - 1 }
}
