import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import type Anthropic from '@anthropic-ai/sdk';
import { formState, loadConfig, isDirty, canUndo, undo } from './formStore';
import type { MidiCaptainConfig } from './types';

// Stands in for the Rust `agent_tool` command.
const agentTool = vi.fn();
vi.mock('./api', () => ({ agentTool: (...args: unknown[]) => agentTool(...args) }));

import { runEditorTool, sendTurn } from './agent';

function makeConfig(label = 'B0'): MidiCaptainConfig {
  return { device: 'one1', active_page: 0, pages: [{ buttons: [{ label, cc: 20, color: 'green' }] }] };
}

const label = () => get(formState).config.pages[0].buttons[0].label;

beforeEach(() => {
  agentTool.mockReset();
  loadConfig(makeConfig());
});

describe('runEditorTool', () => {
  it('sends the tool the config as it would be saved', async () => {
    agentTool.mockResolvedValue({ model: 'one1' });
    await runEditorTool('get_config', {});
    const [name, , config] = agentTool.mock.calls[0];
    expect(name).toBe('get_config');
    expect(JSON.stringify(config)).not.toContain('__uiId');
    expect(config.pages[0].buttons[0].label).toBe('B0');
  });

  it('apply_changes loads the merged config as one undoable, unsaved edit', async () => {
    agentTool.mockResolvedValue({ ok: true, config: makeConfig('FS4') });
    const outcome = await runEditorTool('apply_changes', { pages: [] });

    expect(outcome).toMatchObject({ applied: true, isError: false });
    expect(outcome.content).not.toContain('pages'); // the config isn't echoed back
    expect(label()).toBe('FS4');
    expect(get(isDirty)).toBe(true);

    expect(get(canUndo)).toBe(true);
    undo();
    expect(label()).toBe('B0');
  });

  it('a change the editor validator rejects is not applied and the errors go back to the model', async () => {
    // Passes the Rust side (mocked ok) but the label is empty, an editor-only rule.
    agentTool.mockResolvedValue({ ok: true, config: makeConfig('') });
    const outcome = await runEditorTool('apply_changes', { pages: [] });

    expect(outcome.applied).toBe(false);
    const result = JSON.parse(outcome.content);
    expect(result.ok).toBe(false);
    expect(result.errors.join(' ')).toContain('label');
    expect(label()).toBe('B0');
    expect(get(isDirty)).toBe(false);
  });

  it('a change the Rust side rejects is not applied', async () => {
    agentTool.mockResolvedValue({ ok: false, errors: ['Page 1: expected 1 buttons'] });
    const outcome = await runEditorTool('apply_changes', { pages: [] });
    expect(outcome.applied).toBe(false);
    expect(outcome.content).toContain('expected 1 buttons');
    expect(label()).toBe('B0');
  });

  it('a failed command or unknown tool is a tool error', async () => {
    agentTool.mockRejectedValue({ message: 'Page index 5 is out of range' });
    expect(await runEditorTool('apply_changes', {})).toMatchObject({
      isError: true,
      content: 'Page index 5 is out of range',
    });
    expect(await runEditorTool('list_devices', {})).toMatchObject({ isError: true });
  });
});

// A scripted Messages API: each stream() call returns the next message.
function fakeClient(script: Array<Partial<Anthropic.Message>>) {
  const requests: Anthropic.MessageCreateParams[] = [];
  const client = {
    messages: {
      stream(params: Anthropic.MessageCreateParams) {
        requests.push(structuredClone(params));
        const message = script.shift()!;
        return {
          on(_event: 'text', listener: (delta: string) => void) {
            for (const block of message.content ?? []) if (block.type === 'text') listener(block.text);
          },
          finalMessage: async () => message,
        };
      },
    },
  } as unknown as Anthropic;
  return { client, requests };
}

const text = (t: string) => ({ type: 'text', text: t }) as Anthropic.TextBlock;
const toolUse = (id: string, name: string, input: unknown) =>
  ({ type: 'tool_use', id, name, input }) as Anthropic.ToolUseBlock;

describe('sendTurn', () => {
  beforeEach(() => {
    agentTool.mockImplementation(async (name: string) =>
      name === 'get_schema' ? { title: 'schema' } : { ok: true, config: makeConfig('FS4') },
    );
  });

  it('runs tool calls, returns their results, and stops when the model is done', async () => {
    const { client, requests } = fakeClient([
      { stop_reason: 'tool_use', content: [toolUse('t1', 'apply_changes', { pages: [] })] },
      { stop_reason: 'end_turn', content: [text('Switch 1 is now FS4.')] },
    ]);
    const history: Anthropic.MessageParam[] = [];
    const seen: string[] = [];
    const tools: string[] = [];

    await sendTurn(client, history, 'rename switch 1 to FS4', {
      onText: d => seen.push(d),
      onTool: (name, outcome) => tools.push(`${name}:${outcome.applied}`),
    });

    expect(label()).toBe('FS4');
    expect(seen).toEqual(['Switch 1 is now FS4.']);
    expect(tools).toEqual(['apply_changes:true']);
    expect(history.map(m => m.role)).toEqual(['user', 'assistant', 'user', 'assistant']);

    // The model gets the editor's three tools and the schema in the system prompt.
    expect((requests[0].tools as Anthropic.Tool[]).map(t => t.name)).toEqual(['get_config', 'validate', 'apply_changes']);
    expect(requests[0].system).toContain('"title":"schema"');
    const result = (requests[1].messages[2].content as Anthropic.ToolResultBlockParam[])[0];
    expect(result).toMatchObject({ type: 'tool_result', tool_use_id: 't1', is_error: false });
  });

  it('leaves the conversation untouched when the turn fails', async () => {
    const { client } = fakeClient([{ stop_reason: 'refusal', content: [] }]);
    const history: Anthropic.MessageParam[] = [{ role: 'user', content: 'earlier' }];
    await expect(sendTurn(client, history, 'x', { onText: () => {}, onTool: () => {} })).rejects.toThrow('declined');
    expect(history).toEqual([{ role: 'user', content: 'earlier' }]);
  });

  it('never runs a tool call that was cut off at the token limit', async () => {
    const { client } = fakeClient([
      { stop_reason: 'max_tokens', content: [toolUse('t1', 'apply_changes', { pages: [] })] },
    ]);
    await expect(sendTurn(client, [], 'x', { onText: () => {}, onTool: () => {} })).rejects.toThrow('cut off');
    expect(label()).toBe('B0');
  });
});
