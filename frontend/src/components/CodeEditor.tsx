import Editor from "@monaco-editor/react";
import { useTheme } from "../lib/theme";

export default function CodeEditor({
  value,
  onChange,
  language = "python",
  height = "100%",
}: {
  value: string;
  onChange: (v: string) => void;
  language?: string;
  height?: string | number;
}) {
  const { theme } = useTheme();
  return (
    <div className="h-full overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
      <Editor
        height={height}
        language={language}
        value={value}
        onChange={(v) => onChange(v ?? "")}
        theme={theme === "dark" ? "vs-dark" : "light"}
        options={{
          minimap: { enabled: false },
          fontSize: 13,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          wordWrap: "on",
          padding: { top: 12, bottom: 12 },
        }}
      />
    </div>
  );
}
