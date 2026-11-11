# MCM agent: configure a pedal in plain language (#230)

"Switch 3 toggles CC 52 on channel 1, LED red when on" → the agent reads the config, edits it and writes it back.

| File | Purpose |
|------|---------|
| `tools.json` | Tool names, descriptions and input schemas. Read by the MCP server and (phase 2) the Config Editor chat, so both give the model the same tools. |
| `prompt.md` | Instructions for the model: MCP server `instructions` today, the chat's system prompt in phase 2. |
| `../src-tauri/src/agent.rs` | The tools themselves. Reuses the editor's read, validate and write code. |
| `../src-tauri/src/mcp.rs`, `../src-tauri/src/bin/mcm-mcp.rs` | `mcm-mcp`: the tools as an MCP server on stdio (`rmcp`). |

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
- **Validation is the Rust validator only.** It does not check the contents of keytimes and "Also send" messages, and unknown field names are ignored rather than reported. The editor's TypeScript validator checks more (the open question on #230).
