// The Config Editor's assistant (#230 phase 2): describe a change in plain
// language and it edits the open config. Same tools and prompt as the `mcm-mcp`
// server (`config-editor/agent/`); here they act on the form, not on a file, so
// a change lands as unsaved edits (one undo step) for the user to review and save.

import Anthropic from '@anthropic-ai/sdk';
import { get } from 'svelte/store';
import toolDefinitions from '../../agent/tools.json';
import prompt from '../../agent/prompt.md?raw';
import { agentTool } from './api';
import { formState, normalizeConfig, replaceConfig } from './formStore';
import { validateConfig, validateAllPages } from './validation';
import type { MidiCaptainConfig } from './types';

export const AGENT_MODEL = 'claude-opus-5-5';

// Bounds what one request can spend if the model keeps calling tools.
const MAX_TOOL_ROUNDS = 8;

// `list_devices` has no meaning here (the config is the open form) and the
// schema goes in the system prompt, so the model never needs `get_schema`.
const EDITOR_TOOL_NAMES = ['get_config', 'validate', 'apply_changes'];
const tools = (toolDefinitions as Anthropic.Tool[]).filter(t => EDITOR_TOOL_NAMES.includes(t.name));

const EDITOR_NOTES = `

You are running inside the Config Editor. The config is the one open in the editor: never pass \`target\`. \`apply_changes\` puts your edit in the editor as unsaved changes; the user reviews it and saves it to the pedal themselves, so end by telling them to review and save. The panel shows your reply as plain text: no Markdown. The full config schema follows, so you do not need a \`get_schema\` tool.

`;

let systemPrompt: Promise<string> | null = null;

// Byte-stable across requests, so the prompt cache holds it after the first one.
function getSystemPrompt(): Promise<string> {
  systemPrompt ??= agentTool('get_schema', {}, {}).then(
    schema => prompt + EDITOR_NOTES + JSON.stringify(schema),
  );
  return systemPrompt;
}

/** The config as it would be saved: no editor-only markers or type-irrelevant fields. */
function editorConfig(): MidiCaptainConfig {
  return normalizeConfig(get(formState).config);
}

/** The editor's own checks, which cover rules the Rust validator doesn't (and vice versa). */
function editorErrors(config: MidiCaptainConfig): string[] {
  const active = (config.active_page ?? 0) + 1;
  const activePage = [...validateConfig(config).errors].map(
    ([key, message]) => `${key}: ${message} (page ${active}, or device-wide)`,
  );
  return [...activePage, ...validateAllPages(config)];
}

export interface ToolOutcome {
  content: string;
  isError: boolean;
  /** `apply_changes` changed the form. */
  applied: boolean;
}

/** Run one tool call from the model against the open form. */
export async function runEditorTool(name: string, input: unknown): Promise<ToolOutcome> {
  const args = (input && typeof input === 'object' ? input : {}) as Record<string, unknown>;
  let result: Record<string, unknown>;
  try {
    if (!EDITOR_TOOL_NAMES.includes(name)) throw { message: `Unknown tool '${name}'` };
    result = await agentTool(name, args, editorConfig());
  } catch (e) {
    const message = (e as { message?: string })?.message ?? String(e);
    return { content: message, isError: true, applied: false };
  }

  let applied = false;
  const checked = name === 'apply_changes' ? result.config : name === 'validate' ? args.config : null;
  if (result.ok === true && checked) {
    const errors = editorErrors(checked as MidiCaptainConfig);
    if (errors.length > 0) {
      result = { ok: false, errors };
    } else if (name === 'apply_changes') {
      replaceConfig(checked as MidiCaptainConfig);
      applied = true;
    }
  }
  // The model already has the pages it sent; don't echo the whole config back.
  if (name === 'apply_changes') delete result.config;
  return { content: JSON.stringify(result), isError: false, applied };
}

export function createClient(apiKey: string): Anthropic {
  // The key is the user's own, entered in the panel, so calling the API from
  // the webview exposes it to nobody else.
  return new Anthropic({ apiKey, dangerouslyAllowBrowser: true });
}

export interface TurnEvents {
  /** Streamed assistant text. */
  onText: (delta: string) => void;
  /** A tool ran. */
  onTool: (name: string, outcome: ToolOutcome) => void;
}

/**
 * Send `userText` and run the tool loop until the model finishes its turn.
 * `history` is the conversation so far; it is extended in place on success and
 * left as it was on failure (so a retry doesn't replay a half-finished turn).
 */
export async function sendTurn(
  client: Anthropic,
  history: Anthropic.MessageParam[],
  userText: string,
  events: TurnEvents,
  signal?: AbortSignal,
): Promise<void> {
  const messages: Anthropic.MessageParam[] = [...history, { role: 'user', content: userText }];
  const system = await getSystemPrompt();

  for (let round = 0; ; round++) {
    const stream = client.messages.stream(
      {
        model: AGENT_MODEL,
        max_tokens: 64000,
        // Caches tools + system (the schema) and the conversation so far.
        cache_control: { type: 'ephemeral' },
        system,
        tools,
        messages,
      },
      { signal },
    );
    stream.on('text', events.onText);
    const message = await stream.finalMessage();
    messages.push({ role: 'assistant', content: message.content });

    if (message.stop_reason === 'refusal') throw new Error('The assistant declined this request.');
    // A tool call cut off at the token limit can still parse as a partial
    // object; never run it.
    if (message.stop_reason === 'max_tokens') throw new Error('The reply was cut off. Try a smaller change.');

    const calls = message.content.filter((b): b is Anthropic.ToolUseBlock => b.type === 'tool_use');
    if (calls.length === 0) break;
    if (round >= MAX_TOOL_ROUNDS) throw new Error('The assistant took too many steps. Try a smaller change.');

    const results: Anthropic.ToolResultBlockParam[] = [];
    for (const call of calls) {
      const outcome = await runEditorTool(call.name, call.input);
      events.onTool(call.name, outcome);
      results.push({
        type: 'tool_result',
        tool_use_id: call.id,
        content: outcome.content,
        is_error: outcome.isError,
      });
    }
    messages.push({ role: 'user', content: results });
  }

  history.splice(0, history.length, ...messages);
}

/** A message for the panel from anything `sendTurn` can throw. */
export function describeError(error: unknown): string {
  if (error instanceof Anthropic.APIUserAbortError) return 'Stopped.';
  if (error instanceof Anthropic.AuthenticationError) return 'That API key was rejected. Check the key and try again.';
  if (error instanceof Anthropic.PermissionDeniedError) return 'This API key is not allowed to use the assistant model.';
  if (error instanceof Anthropic.RateLimitError) return 'Rate limited by the API. Wait a moment and try again.';
  if (error instanceof Anthropic.APIConnectionError) return 'Could not reach the API. Check your connection.';
  if (error instanceof Anthropic.APIError) return `API error ${error.status ?? ''}: ${error.message}`;
  return error instanceof Error ? error.message : String(error);
}
