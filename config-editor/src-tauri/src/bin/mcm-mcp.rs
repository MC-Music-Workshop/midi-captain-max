//! MCP server for configuring a MIDI Captain from an MCP client (#230).
//! See `config-editor/agent/README.md` for client setup.

fn main() {
    if let Err(e) = config_editor_lib::mcp::serve_stdio() {
        // stdout carries the protocol; errors go to stderr.
        eprintln!("mcm-mcp: {e}");
        std::process::exit(1);
    }
}
