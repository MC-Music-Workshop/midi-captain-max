import { defineConfig } from 'vitepress'
import path from 'node:path'

// srcDir lives outside this package (../docs/user), so Vite can't resolve
// vue by walking up from the markdown files; alias it explicitly.
const require_ = (await import('node:module')).createRequire(import.meta.url)
const vueDir = path.dirname(require_.resolve('vue/package.json'))

// User-facing docs for MIDI Captain MAX.
// Markdown source of truth lives in ../docs/user (readable on GitHub);
// this folder only holds the VitePress build config and theme overrides.
//
// Deployed under the /docs/ subpath of the existing GitHub Pages site.
// If the site ever moves to a custom domain, change `base` to '/docs/'.
export default defineConfig({
  srcDir: '../docs/user',
  vite: {
    resolve: {
      alias: [
        { find: /^vue$/, replacement: path.join(vueDir, 'dist/vue.runtime.esm-bundler.js') },
        { find: /^vue\/server-renderer$/, replacement: require_.resolve('vue/server-renderer') },
      ],
    },
  },
  outDir: './dist',
  base: '/midi-captain-max/docs/',

  title: 'MIDI Captain MAX',
  description: 'User documentation for MIDI Captain MAX (MCM) — open firmware and config editor for the PaintAudio MIDI Captain.',

  appearance: 'dark',
  cleanUrls: true,

  themeConfig: {
    nav: [
      // Escapes the /docs/ base to reach the hand-built landing page one
      // level up. Relative (not "/midi-captain-max/"), so it isn't
      // base-prefixed by VitePress and survives a custom domain move.
      // target forces a real browser navigation: the landing page isn't
      // part of this VitePress build, so the SPA router's click handler
      // would otherwise intercept it and fail to find a matching route.
      { text: 'Home', link: '../', target: '_self' },
      { text: 'GitHub', link: 'https://github.com/MC-Music-Workshop/midi-captain-max' },
    ],
    sidebar: [
      {
        text: 'Guides',
        items: [
          { text: 'Installation', link: '/installation' },
          { text: 'Keytimes', link: '/keytimes' },
          { text: 'Inbound MIDI', link: '/inbound-midi' },
          { text: 'Page Control (MIDI-IN)', link: '/page-control' },
          { text: 'MIDI Routing Matrix', link: '/midi-thru' },
        ],
      },
    ],
    search: { provider: 'local' },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/MC-Music-Workshop/midi-captain-max' },
    ],
    outline: 'deep',
  },
})
