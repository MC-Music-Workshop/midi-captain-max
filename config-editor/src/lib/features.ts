// Features that are on main but not released yet.
//
// The Assistant (#230) shows in `tauri dev`. Any other build hides it unless it
// is built with VITE_MCM_ASSISTANT=1 (e.g. `VITE_MCM_ASSISTANT=1 npm run tauri build`).
export const ASSISTANT_ENABLED: boolean =
  import.meta.env.DEV || import.meta.env.VITE_MCM_ASSISTANT === '1';
