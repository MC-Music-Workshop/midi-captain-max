import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import './custom.css'

// Click-to-enlarge for screenshots. Editor screenshots are wide, so at page
// width they shrink below readable; clicking one overlays it at full size.
// Delegated from document, so it covers images added to any page later.
function enableImageZoom() {
  const overlay = document.createElement('div')
  overlay.className = 'img-zoom-overlay'
  overlay.setAttribute('role', 'dialog')
  overlay.setAttribute('aria-label', 'Enlarged image')
  const zoomed = document.createElement('img')
  overlay.appendChild(zoomed)
  document.body.appendChild(overlay)

  const close = () => overlay.classList.remove('open')

  document.addEventListener('click', (e) => {
    const target = e.target as HTMLElement
    if (overlay.classList.contains('open')) return close()
    // Only content images, and not ones the author already wrapped in a link.
    if (target.tagName !== 'IMG' || !target.closest('.vp-doc')) return
    if (target.closest('a')) return
    zoomed.src = (target as HTMLImageElement).src
    zoomed.alt = (target as HTMLImageElement).alt
    overlay.classList.add('open')
  })

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close()
  })
}

export default {
  extends: DefaultTheme,
  enhanceApp() {
    // SSR builds have no document; the browser runs this on hydration.
    if (typeof document !== 'undefined') enableImageZoom()
  },
} satisfies Theme
