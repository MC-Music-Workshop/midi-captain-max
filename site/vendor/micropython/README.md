# Vendored MicroPython WebAssembly build

- Package: [`@micropython/micropython-webassembly-pyscript`](https://www.npmjs.com/package/@micropython/micropython-webassembly-pyscript)
- Version: **1.28.0-6** (MicroPython 1.28.0, official webassembly port build)
- Files: `micropython.mjs` (loader, resolves the `.wasm` relative to itself) and `micropython.wasm`

The home page lazy-loads this runtime to run the literal firmware modules in
`site/firmware/` (see `docs/plans/2026-07-05-live-firmware-demo-plan.md`).

To update:

```bash
curl -sL "$(curl -s https://registry.npmjs.org/@micropython/micropython-webassembly-pyscript | jq -r '.versions[.["dist-tags"].latest].dist.tarball')" | tar xz
cp package/micropython.mjs package/micropython.wasm site/vendor/micropython/
```

Then bump the version above.
