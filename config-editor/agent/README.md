# MCM agent: configure a pedal in plain language (#230)

"Switch 3 toggles CC 52 on channel 1, LED red when on" → the agent reads the config, edits it and writes it back.

| File | Purpose |
|------|---------|
| `tools.json` | Tool names, descriptions and input schemas. Read by the MCP server and the Config Editor's Assistant panel, so both give the model the same tools. |
| `prompt.md` | Instructions for the model: the MCP server's `instructions` and the start of the Assistant's system prompt. |
| `../src-tauri/src/agent.rs` | The tools themselves. Reuses the editor's read, validate and write code. |
| `../src-tauri/src/mcp.rs`, `../src-tauri/src/bin/mcm-mcp.rs` | `mcm-mcp`: the tools as an MCP server on stdio (`rmcp`). |
| `../src/lib/agent.ts`, `../src/lib/components/AgentChat.svelte` | The in-app Assistant: Claude tool loop (`@anthropic-ai/sdk`) and its panel. |

## Try it from Claude Code or Claude Desktop

**How:** build the server once:

```bash
cd config-editor/src-tauri
cargo build --release --bin mcm-mcp     # → target/release/mcm-mcp
```

A fresh worktree needs `tools/bundle-firmware-for-dev.sh` first (the crate's build script wants the staged firmware resources).

Claude Code:

```bash
claude mcp add mcm -- /absolute/path/to/config-editor/src-tauri/target/release/mcm-mcp
```

Claude Desktop, in `claude_desktop_config.json`:

```json
{ "mcpServers": { "mcm": { "command": "/absolute/path/to/config-editor/src-tauri/target/release/mcm-mcp" } } }
```

Then ask for a change. With one pedal connected (drive mounted) no path is needed; otherwise name a saved config file.

## Tools

| Tool | Does |
|------|------|
| `list_devices` | Connected pedals: name, path, model |
| `get_schema(definition?)` | `config.schema.json`, or one definition |
| `get_config(target?)` | Config JSON, model, page count, buttons per page |
| `validate(config)` | `ok`, or the Rust validator's errors |
| `apply_changes(target?, pages?, globals?)` | Merge → validate → back up → write, only if valid |

`target` is a pedal drive path or a config file path. When omitted, the only connected pedal is used.

## Behavior worth knowing

- **Nothing is written unless the merged config validates.** Errors come back to the model so it can correct them.
- **The previous config is copied to `~/Documents/MIDICaptainMAX/backups/<name>-<timestamp>.json`** before each write. To roll back, load that file in the Config Editor and Save to Device.
- **The raw JSON is written**, never a re-serialized struct, so fields the Rust structs don't model survive (#215).
- **A pedal loads the new config on its next restart.** There is no restart tool in v1.
- **A host file is only overwritten when it is already a MIDI Captain config** (has a known `device`), so a wrong path can't clobber an unrelated JSON file.
- **Pages can be replaced or appended, not deleted or reordered** (page jumps aren't remapped today).
- **Validation is two passes:** `config.schema.json` (the `jsonschema` crate: ranges, patterns, message contents, unknown field names, with JSON paths), then `MidiCaptainConfig::validate` for the cross-field rules. The Rust validator alone misses message contents and misspelled fields.

## In the Config Editor (Assistant panel)

The toolbar's **Assistant** button opens a chat panel (`AgentChat.svelte`). User-facing description: [`docs/user/assistant.md`](../../docs/user/assistant.md).

| MCP tool | In the editor |
|----------|---------------|
| `get_schema` | Not a tool: the schema is appended to the system prompt (cached) |
| `get_config` | The form's config as it would be saved (`normalizeConfig`) |
| `validate` | Rust `agent::validate`, then the editor's `validateConfig` + `validateAllPages` |
| `apply_changes` | Rust merges and validates in memory, the editor validators run, then `replaceConfig` loads it as one undo step. Nothing is written; the user saves |
| `list_devices` | Not offered |

- **One Rust command, `agent_tool`** (`agent::call_editor_tool`), runs the tools against the config the frontend passes in, so merge and validation are the same code the MCP server uses.
- **Model and limits** are constants in `agent.ts`: `claude-opus-5-5`, 8 tool rounds per request.
- **API access is bring-your-own-key for now.** The key lives in the OS credential store (`src-tauri/src/secrets.rs`, `keyring` crate: macOS Keychain, Windows Credential Manager, Secret Service on Linux), the panel holds it in memory only, and the webview calls `api.anthropic.com` directly (`connect-src` in `tauri.conf.json`). The planned proxy replaces the key with a `baseURL` on the client in `createClient`.
- **A failed request leaves the conversation as it was**, so a retry doesn't replay half a turn; an edit already applied stays in the form (Undo reverts it).
