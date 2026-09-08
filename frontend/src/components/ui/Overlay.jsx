import { createPortal } from 'react-dom'
import { createContext, forwardRef, useContext } from 'react'

const OverlayLayer = createContext(990)

// Dialogs live above the app shell, outside scrolling and animated pages.
export default forwardRef(function Overlay({ children, layer, style, ...props }, ref) {
  const parentLayer = useContext(OverlayLayer)
  const currentLayer = layer ?? style?.zIndex ?? parentLayer + 10
  return createPortal(
    <OverlayLayer.Provider value={currentLayer}>
      <div {...props} ref={ref} style={{ ...style, zIndex: currentLayer }}>{children}</div>
    </OverlayLayer.Provider>,
    document.body,
  )
})
