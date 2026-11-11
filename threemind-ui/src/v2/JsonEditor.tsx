import { useEffect, useRef } from "react";
import { t, useLocale } from "./i18n";
import { EditorState, Compartment, type Extension } from "@codemirror/state";
import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  highlightActiveLineGutter,
  drawSelection,
} from "@codemirror/view";
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
} from "@codemirror/commands";
import { json, jsonLanguage, jsonParseLinter } from "@codemirror/lang-json";
import {
  syntaxHighlighting,
  defaultHighlightStyle,
  foldGutter,
  bracketMatching,
  indentOnInput,
} from "@codemirror/language";
import { lintGutter, linter } from "@codemirror/lint";
import {
  searchKeymap,
  highlightSelectionMatches,
  searchPanelOpen,
  closeSearchPanel,
  openSearchPanel,
} from "@codemirror/search";
import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";

export function parseJson(text: string): any {
  const result = JSON.parse(text);
  // JSON.parse otherwise silently keeps only the last occurrence of a key.
  jsonLanguage.parser.parse(text).iterate({
    enter(node) {
      if (node.name !== "Object") return;
      const keys = new Set<string>();
      for (
        let property = node.node.firstChild;
        property;
        property = property.nextSibling
      ) {
        if (property.name !== "Property") continue;
        const key = property.firstChild!;
        const name = JSON.parse(text.slice(key.from, key.to));
        if (keys.has(name))
          throw new Error(
            t("第 {line} 行：键 {key} 重复，请保留唯一值。", {
              line: text.slice(0, key.from).split("\n").length,
              key: String(name),
            }),
          );
        keys.add(name);
      }
    },
  });
  return result;
}

export default function JsonEditor({
  value,
  onChange,
  rows = 12,
  readOnly = false,
  label = t("JSON 参数"),
  syntaxExtensions,
}: {
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  readOnly?: boolean;
  label?: string;
  syntaxExtensions?: Extension[];
}) {
  const host = useRef<HTMLDivElement>(null),
    view = useRef<EditorView | null>(null);
  const callback = useRef(onChange),
    external = useRef(false),
    editable = useRef(new Compartment()),
    localized = useRef(new Compartment());
  const language = useLocale();
  const localization = () => [
    EditorView.contentAttributes.of({
      "aria-label": label,
      role: "textbox",
      "aria-multiline": "true",
      spellcheck: "false",
    }),
    EditorState.phrases.of(
      language === "zh-CN"
        ? {
            Find: "查找",
            Replace: "替换",
            next: "下一处",
            previous: "上一处",
            all: "全部",
            "match case": "区分大小写",
            regexp: "正则表达式",
            "by word": "完整单词",
            replace: "替换",
            "replace all": "全部替换",
            close: "关闭",
            "Go to line": "跳转到行",
            go: "跳转",
            "current match": "当前匹配",
            "on line": "所在行",
            "replaced match on line $": "已替换第 $ 行匹配",
            "replaced $ matches": "已替换 $ 处匹配",
            "Folded lines": "已折叠行",
            "Unfolded lines": "已展开行",
            to: "至",
            "folded code": "已折叠代码",
            unfold: "展开",
            "Fold line": "折叠行",
            "Unfold line": "展开行",
            Diagnostics: "诊断",
            "No diagnostics": "没有诊断问题",
          }
        : {},
    ),
  ];
  callback.current = onChange;
  useEffect(() => {
    const editor = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(),
          highlightActiveLineGutter(),
          history(),
          drawSelection(),
          foldGutter(),
          indentOnInput(),
          bracketMatching(),
          closeBrackets(),
          highlightActiveLine(),
          highlightSelectionMatches(),
          syntaxHighlighting(defaultHighlightStyle),
          ...(syntaxExtensions ?? [
            json(),
            lintGutter(),
            linter(jsonParseLinter()),
          ]),
          keymap.of([
            ...closeBracketsKeymap,
            ...defaultKeymap,
            ...historyKeymap,
            ...searchKeymap,
            indentWithTab,
          ]),
          editable.current.of([
            EditorState.readOnly.of(readOnly),
            EditorView.editable.of(!readOnly),
          ]),
          localized.current.of(localization()),
          EditorView.updateListener.of((update) => {
            if (update.docChanged && !external.current)
              callback.current(update.state.doc.toString());
          }),
          EditorView.theme({
            "&": {
              fontSize: "12px",
              backgroundColor: "var(--panel)",
              color: "var(--text)",
            },
            ".cm-scroller": {
              fontFamily: "Consolas, monospace",
              minHeight: `${rows * 20}px`,
              maxHeight: "440px",
              overflow: "auto",
            },
            ".cm-content": { padding: "12px 0", caretColor: "var(--accent)" },
            ".cm-gutters": {
              backgroundColor: "var(--bg)",
              color: "var(--muted)",
              borderColor: "var(--border)",
            },
            ".cm-activeLine, .cm-activeLineGutter": {
              backgroundColor: "#55887514",
            },
            "&.cm-focused": {
              outline: "2px solid var(--accent)",
              outlineOffset: "-2px",
            },
          }),
        ],
      }),
    });
    view.current = editor;
    return () => {
      view.current = null;
      editor.destroy();
    };
  }, []);
  useEffect(() => {
    const editor = view.current;
    if (editor && editor.state.doc.toString() !== value) {
      external.current = true;
      editor.dispatch({
        changes: { from: 0, to: editor.state.doc.length, insert: value },
      });
      external.current = false;
    }
  }, [value]);
  useEffect(() => {
    view.current?.dispatch({
      effects: editable.current.reconfigure([
        EditorState.readOnly.of(readOnly),
        EditorView.editable.of(!readOnly),
      ]),
    });
  }, [readOnly]);
  useEffect(() => {
    const editor = view.current;
    if (!editor) return;
    const panelOpen = searchPanelOpen(editor.state);
    const active = document.activeElement;
    const restoreFocus =
      active instanceof HTMLElement && !editor.dom.contains(active);
    // A paste can still be pending until keyup/change in CodeMirror's panel.
    // Commit its fields before rebuilding the panel with translated phrases.
    if (panelOpen)
      editor.dom
        .querySelector<HTMLInputElement>('.cm-search input[name="search"]')
        ?.dispatchEvent(new Event("change", { bubbles: true }));
    editor.dispatch({
      effects: localized.current.reconfigure(localization()),
    });
    // CodeMirror constructs panel phrases once. Reopen only its search panel;
    // the query, document, selection and undo history remain in the same state.
    if (panelOpen) {
      closeSearchPanel(editor);
      openSearchPanel(editor);
      if (restoreFocus && active.isConnected)
        active.focus({ preventScroll: true });
    }
  }, [language, label]);
  return <div className="json-editor" ref={host} />;
}
