# Assistant: Describe a Change in Plain Language

Instead of filling in the fields yourself, you can tell the Config Editor what you want and let the assistant make the edit.

> **Not in released builds yet.** This page is unlinked from the guide index until the Assistant ships.
>
> **Early version.** The assistant runs on your own Anthropic API key, and you pay Anthropic for what it uses. Your config is sent to Anthropic with each request.

## How to use it

1. Open a config (from a device, a file, or a new one).
2. Click **Assistant** in the toolbar. A panel opens on the right.
3. The first time, paste your Anthropic API key and click **Use this key**. The key is stored in your computer's keychain (macOS Keychain, Windows Credential Manager, or the Linux secret service). **Change API key** removes it.
4. Describe the change and press Enter. For example:
   - "Switch 3 toggles CC 52 on channel 1, red when on."
   - "Make switch 1 on page 2 a momentary note 60."
   - "Add a page like page 1 but on channel 3."
5. When the panel says **Config changed**, look over the edit in the editor, then save as usual (**Save to Device** or **Save to File**).

## What to expect

- **Nothing is saved for you.** The assistant's edit shows up as unsaved changes, exactly as if you had typed it. **Undo** reverts it in one step.
- **It asks instead of guessing.** If you name a target such as "Helix FS4" without the CC number and channel, it asks you for them.
- **Invalid changes are not applied.** The edit goes through the same checks as the form; if it fails, the assistant tries to correct it or tells you what is wrong.
- **It can change and add pages, but not delete or reorder them.** Use **Edit Pages** for that.
- **Stop** cancels a request that is taking too long.
