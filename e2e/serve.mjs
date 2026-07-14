// Minimal static file server for the home page during E2E tests.
//
// Why not `python -m http.server`: the demo loads an ES module
// (vendor/micropython/micropython.mjs) and a .wasm binary, both of which the
// browser only accepts with the correct MIME type — a wrong type makes the
// `import()` or WebAssembly instantiation fail and the whole wasm engine
// silently falls back. This server sets those types explicitly.
//
// Usage: node serve.mjs [port]   (serves ../site)
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "site");
const PORT = Number(process.argv[2] || process.env.PORT || 4173);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".wasm": "application/wasm",
  ".json": "application/json",
  ".py": "text/plain; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".css": "text/css",
};

http
  .createServer((req, res) => {
    const rel = decodeURIComponent(req.url.split("?")[0]);
    const filePath = path.join(ROOT, rel === "/" ? "index.html" : rel);
    // Contain traversal to ROOT.
    if (!filePath.startsWith(ROOT)) {
      res.writeHead(403);
      res.end();
      return;
    }
    let data;
    try {
      data = fs.readFileSync(filePath);
    } catch {
      res.writeHead(404);
      res.end("not found");
      return;
    }
    res.writeHead(200, { "content-type": MIME[path.extname(filePath)] || "application/octet-stream" });
    res.end(data);
  })
  .listen(PORT, () => console.log(`serving ${ROOT} on http://localhost:${PORT}`));
