//! `mcm-mcp`: the agent tools (`config_editor_lib::agent`) as an MCP server on
//! stdio (#230), so Claude Desktop / Claude Code can configure a pedal from plain
//! language. See `config-editor/agent/README.md` for client setup.
//!
//! A separate crate, not a second binary of the app: Tauri's bundler packages
//! every binary of the app crate, which broke the universal macOS build and put
//! this server inside the app on the other platforms.
//!
//! The tool list is `agent/tools.json` rather than `rmcp`'s `#[tool]` macros:
//! the Config Editor's chat hands the model the same file.

use config_editor_lib::agent;
use rmcp::model::{
    CallToolRequestParams, CallToolResponse, CallToolResult, ContentBlock, Implementation, ListToolsResult,
    PaginatedRequestParams,
    ServerCapabilities, ServerConfig, Tool,
};
use rmcp::service::RequestContext;
use rmcp::{ErrorData, RoleServer, ServerHandler, ServiceExt};
use serde_json::{Map, Value};

fn tools() -> Vec<Tool> {
    let definitions: Vec<Value> = serde_json::from_str(agent::TOOLS_JSON).expect("agent/tools.json is valid JSON");
    definitions
        .into_iter()
        .map(|mut t| {
            Tool::new(
                t["name"].as_str().expect("tool name").to_string(),
                t["description"].as_str().expect("tool description").to_string(),
                rmcp::model::object(t["input_schema"].take()),
            )
        })
        .collect()
}

/// Tool results are JSON text. A failed call is a tool error (`isError`), which
/// the model reads and can correct, not a protocol error.
fn call(name: &str, args: &Map<String, Value>) -> CallToolResult {
    match agent::call_tool(name, args) {
        Ok(value) => CallToolResult::success(vec![ContentBlock::text(
            serde_json::to_string_pretty(&value).unwrap_or_else(|e| e.to_string()),
        )]),
        Err(e) => {
            let mut text = e.message;
            for detail in e.details.unwrap_or_default() {
                text.push_str("\n- ");
                text.push_str(&detail);
            }
            CallToolResult::error(vec![ContentBlock::text(text)])
        }
    }
}

struct McmServer;

impl ServerHandler for McmServer {
    fn get_info(&self) -> ServerConfig {
        ServerConfig::new(ServerCapabilities::builder().enable_tools().build())
            .with_server_info(Implementation::new("mcm-mcp", env!("CARGO_PKG_VERSION")))
            .with_instructions(agent::PROMPT)
    }

    async fn list_tools(
        &self,
        _request: Option<PaginatedRequestParams>,
        _context: RequestContext<RoleServer>,
    ) -> Result<ListToolsResult, ErrorData> {
        Ok(ListToolsResult::with_all_items(tools()))
    }

    async fn call_tool(
        &self,
        request: CallToolRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> Result<CallToolResponse, ErrorData> {
        Ok(call(&request.name, &request.arguments.unwrap_or_default()).into())
    }
}

/// Serve on stdin/stdout until the client disconnects.
fn serve_stdio() -> Result<(), Box<dyn std::error::Error>> {
    tokio::runtime::Builder::new_current_thread().enable_all().build()?.block_on(async {
        McmServer.serve(rmcp::transport::stdio()).await?.waiting().await?;
        Ok(())
    })
}

fn main() {
    if let Err(e) = serve_stdio() {
        // stdout carries the protocol; errors go to stderr.
        eprintln!("mcm-mcp: {e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_tool_definition_becomes_an_mcp_tool() {
        let names: Vec<String> = tools().into_iter().map(|t| t.name.to_string()).collect();
        assert_eq!(names, ["list_devices", "get_schema", "get_config", "validate", "apply_changes"]);
    }

    #[test]
    fn a_failed_call_is_a_tool_error_with_the_message() {
        let result = call("get_schema", serde_json::json!({ "definition": "Nope" }).as_object().unwrap());
        assert_eq!(result.is_error, Some(true));
        let ok = call("get_schema", serde_json::json!({ "definition": "Page" }).as_object().unwrap());
        assert_ne!(ok.is_error, Some(true));
    }
}
