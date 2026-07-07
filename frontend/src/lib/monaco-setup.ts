// Bundle Monaco locally (no CDN) so the editor works offline / under a strict CSP.
// Importing `monaco-editor` pulls in the basic-language tokenizers (python, sql, shell,
// yaml, json...), so syntax highlighting works with just the base editor worker.
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import jsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(self as any).MonacoEnvironment = {
  getWorker(_workerId: string, label: string) {
    if (label === "json") return new jsonWorker();
    return new editorWorker();
  },
};

loader.config({ monaco });

export const MONACO_LANGUAGE: Record<string, string> = {
  python: "python",
  sql: "sql",
  shell: "shell",
  yaml: "yaml",
  json: "json",
  text: "plaintext",
};
