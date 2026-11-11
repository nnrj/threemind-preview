import { useEffect, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import { markdown } from "@codemirror/lang-markdown";
import {
  Bold,
  Italic,
  Underline,
  List,
  ListOrdered,
  Quote,
  Code,
  ImagePlus,
  Link2,
  Undo2,
  Redo2,
  Maximize2,
  Minimize2,
  Highlighter,
  ListChecks,
} from "lucide-react";
import { noteExtensions, toNoteMarkdown, emptyDocument } from "./noteDocument";
import { api } from "./api";
import { t, useLocale } from "./i18n";
import { Button, ErrorBox, Field, Modal } from "./ui";
import JsonEditor from "./JsonEditor";
import type { NoteBody } from "./noteStore";
import "katex/dist/katex.min.css";

const markdownSyntax = [markdown()];
export default function NoteEditor({
  value,
  onChange,
  project,
  readOnly = false,
  beforeSwitch,
}: {
  value: NoteBody;
  onChange: (value: NoteBody) => void;
  project: string;
  readOnly?: boolean;
  beforeSwitch?: () => Promise<boolean>;
}) {
  useLocale();
  const callback = useRef(onChange),
    current = useRef(value),
    syncing = useRef(false);
  callback.current = onChange;
  const [full, setFull] = useState(false),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<"link" | "math" | null>(null),
    [input, setInput] = useState(""),
    [blockMath, setBlockMath] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const root = useRef<HTMLElement>(null);
  const readOnlyRef = useRef(readOnly);
  readOnlyRef.current = readOnly || busy;
  const [mathPosition, setMathPosition] = useState<number | null>(null);
  const editor = useEditor({
    extensions: noteExtensions((latex, position, block) => {
      if (readOnlyRef.current) return;
      setInput(latex);
      setMathPosition(position);
      setBlockMath(block);
      setDialog("math");
    }),
    content: value.format === "document" ? value.content : emptyDocument(),
    editable: !readOnly,
    shouldRerenderOnTransaction: true,
    editorProps: {
      attributes: {
        "aria-label": t("文档正文"),
        role: "textbox",
        "aria-multiline": "true",
      },
    },
    onUpdate: ({ editor }) => {
      if (!syncing.current && current.current.format === "document") {
        const body: NoteBody = {
          format: "document",
          content: editor.getJSON(),
        };
        current.current = body;
        callback.current(body);
      }
    },
  });
  useEffect(() => {
    editor?.setEditable(!readOnly && !busy, false);
  }, [editor, readOnly, busy]);
  useEffect(() => {
    if (editor && value !== current.current && value.format === "document") {
      syncing.current = true;
      editor.commands.setContent(value.content, { emitUpdate: false });
      syncing.current = false;
    }
    current.current = value;
  }, [editor, value]);
  useEffect(() => {
    editor?.setOptions({
      editorProps: {
        attributes: {
          "aria-label": t("文档正文"),
          role: "textbox",
          "aria-multiline": "true",
        },
      },
    });
    root.current
      ?.querySelectorAll<HTMLInputElement>(
        'li[data-checked] input[type="checkbox"]',
      )
      .forEach((input) => {
        const text =
          input.closest("li")?.querySelector(":scope > div")?.textContent ||
          t("空白任务");
        const label = t("任务：{text}", { text });
        input.setAttribute("aria-label", label);
        const span = input.parentElement?.querySelector("span");
        if (span) span.textContent = label;
      });
  }, [editor, t("文档正文")]);
  useEffect(() => {
    if (!full) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFull(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [full]);
  const switchMode = async () => {
    if (!editor) return;
    setError(null);
    setBusy(true);
    try {
      // Preserve the original authoritative source in a saved revision before conversion.
      const next: NoteBody =
        value.format === "document"
          ? {
              format: "markdown",
              text: toNoteMarkdown(editor, value.content).text,
            }
          : { format: "document", content: editor.markdown!.parse(value.text) };
      if (beforeSwitch && !(await beforeSwitch())) return;
      if (next.format === "document") {
        syncing.current = true;
        editor.commands.setContent(next.content, { emitUpdate: false });
        syncing.current = false;
      }
      current.current = next;
      onChange(next);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const upload = async (image: File) => {
    setError(null);
    setBusy(true);
    try {
      if (image.size > 8 * 1024 * 1024)
        throw new Error(t("图片不能超过 8 MiB。"));
      const id = crypto.randomUUID();
      await api(
        `/projects/${project}/note-assets/${id}?filename=${encodeURIComponent(image.name.slice(0, 200))}`,
        {
          method: "PUT",
          body: image,
          headers: { "Content-Type": image.type || "application/octet-stream" },
        },
      );
      const src = `/api/v2/projects/${project}/note-assets/${id}`;
      if (current.current.format === "markdown")
        onChange({
          format: "markdown",
          text:
            current.current.text +
            `\n\n![${image.name.replace(/[\[\]\\\r\n]/g, "")}](${src})\n`,
        });
      else editor?.chain().focus().setImage({ src, alt: image.name }).run();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  };
  const tool = (
    name: string,
    Icon: typeof Bold,
    action: () => void,
    active = false,
    disabled = false,
  ) => (
    <button
      type="button"
      className={`note-tool ${active ? "active" : ""}`}
      title={name}
      aria-label={name}
      aria-pressed={active}
      disabled={readOnly || busy || disabled}
      onClick={action}
    >
      <Icon size={17} />
    </button>
  );
  return (
    <section
      ref={root}
      className={`note-editor ${full ? "note-fullscreen" : ""}`}
      aria-label={t("双模式编辑器")}
    >
      <div className="note-editor-bar">
        <div className="note-mode" role="group" aria-label={t("编辑模式")}>
          <Button
            aria-pressed={value.format === "markdown"}
            disabled={busy || readOnly || value.format === "markdown"}
            onClick={switchMode}
          >
            Markdown
          </Button>
          <Button
            aria-pressed={value.format === "document"}
            disabled={busy || readOnly || value.format === "document"}
            onClick={switchMode}
          >
            {t("文档")}
          </Button>
        </div>
        <div className="note-editor-actions">
          <span className="muted">
            {value.format === "markdown"
              ? t("行号 · 语法高亮 · 查找替换")
              : t("所见即所得 · 表格 · 公式")}
          </span>
          <button
            type="button"
            className="note-tool"
            aria-label={full ? t("退出全屏") : t("全屏编辑")}
            onClick={() => setFull(!full)}
          >
            {full ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </button>
        </div>
      </div>
      <ErrorBox error={error} />
      {value.format === "markdown" ? (
        <>
          <div className="note-source-help">
            <span>
              {t(
                "富文本样式会以 HTML 片段保留。切换前保存原稿；文档模式只支持编辑器识别的格式。",
              )}
            </span>
            <Button
              disabled={readOnly || busy}
              onClick={() => file.current?.click()}
            >
              <ImagePlus size={15} />
              {t("插入图片")}
            </Button>
          </div>
          <JsonEditor
            value={value.text}
            onChange={(text) => onChange({ format: "markdown", text })}
            label={t("Markdown 正文")}
            rows={22}
            readOnly={readOnly || busy}
            syntaxExtensions={markdownSyntax}
          />
        </>
      ) : (
        editor && (
          <>
            <div
              className="note-toolbar"
              role="toolbar"
              aria-label={t("文档格式")}
            >
              <select
                aria-label={t("段落样式")}
                disabled={readOnly || busy}
                value={
                  editor.isActive("heading")
                    ? editor.getAttributes("heading").level
                    : "paragraph"
                }
                onChange={(e) =>
                  e.target.value === "paragraph"
                    ? editor.chain().focus().setParagraph().run()
                    : editor
                        .chain()
                        .focus()
                        .toggleHeading({
                          level: Number(e.target.value) as 1 | 2 | 3,
                        })
                        .run()
                }
              >
                <option value="paragraph">{t("正文")}</option>
                <option value="1">{t("标题 1")}</option>
                <option value="2">{t("标题 2")}</option>
                <option value="3">{t("标题 3")}</option>
              </select>
              <select
                aria-label={t("字体")}
                disabled={readOnly || busy}
                value={editor.getAttributes("textStyle").fontFamily || ""}
                onChange={(e) =>
                  e.target.value
                    ? editor.chain().focus().setFontFamily(e.target.value).run()
                    : editor.chain().focus().unsetFontFamily().run()
                }
              >
                <option value="">{t("默认字体")}</option>
                <option value="serif">{t("衬线字体")}</option>
                <option value="sans-serif">{t("无衬线字体")}</option>
                <option value="monospace">{t("等宽字体")}</option>
              </select>
              <select
                aria-label={t("字号")}
                disabled={readOnly || busy}
                value={editor.getAttributes("textStyle").fontSize || ""}
                onChange={(e) =>
                  e.target.value
                    ? editor.chain().focus().setFontSize(e.target.value).run()
                    : editor.chain().focus().unsetFontSize().run()
                }
              >
                <option value="">{t("默认字号")}</option>
                {[12, 14, 16, 18, 24, 32].map((n) => (
                  <option key={n} value={`${n}px`}>
                    {n}
                  </option>
                ))}
              </select>
              {tool(
                t("撤销"),
                Undo2,
                () => editor.chain().focus().undo().run(),
                false,
                !editor.can().undo(),
              )}
              {tool(
                t("重做"),
                Redo2,
                () => editor.chain().focus().redo().run(),
                false,
                !editor.can().redo(),
              )}
              {tool(
                t("粗体"),
                Bold,
                () => editor.chain().focus().toggleBold().run(),
                editor.isActive("bold"),
              )}
              {tool(
                t("斜体"),
                Italic,
                () => editor.chain().focus().toggleItalic().run(),
                editor.isActive("italic"),
              )}
              {tool(
                t("下划线"),
                Underline,
                () => editor.chain().focus().toggleUnderline().run(),
                editor.isActive("underline"),
              )}
              {tool(
                t("高亮"),
                Highlighter,
                () =>
                  editor
                    .chain()
                    .focus()
                    .toggleHighlight({ color: "#ffe68a" })
                    .run(),
                editor.isActive("highlight"),
              )}
              <input
                type="color"
                title={t("文字颜色")}
                aria-label={t("文字颜色")}
                disabled={readOnly || busy}
                value={
                  /^#[\da-f]{6}$/i.test(
                    editor.getAttributes("textStyle").color || "",
                  )
                    ? editor.getAttributes("textStyle").color
                    : "#237969"
                }
                onChange={(e) =>
                  editor.chain().focus().setColor(e.target.value).run()
                }
              />
              <select
                aria-label={t("对齐方式")}
                disabled={readOnly || busy}
                value={
                  editor.getAttributes("paragraph").textAlign ||
                  editor.getAttributes("heading").textAlign ||
                  "left"
                }
                onChange={(e) =>
                  editor.chain().focus().setTextAlign(e.target.value).run()
                }
              >
                <option value="left">{t("左对齐")}</option>
                <option value="center">{t("居中")}</option>
                <option value="right">{t("右对齐")}</option>
                <option value="justify">{t("两端对齐")}</option>
              </select>
              {tool(
                t("无序列表"),
                List,
                () => editor.chain().focus().toggleBulletList().run(),
                editor.isActive("bulletList"),
              )}
              {tool(
                t("有序列表"),
                ListOrdered,
                () => editor.chain().focus().toggleOrderedList().run(),
                editor.isActive("orderedList"),
              )}
              {tool(
                t("任务清单"),
                ListChecks,
                () => editor.chain().focus().toggleTaskList().run(),
                editor.isActive("taskList"),
              )}
              {tool(
                t("引用"),
                Quote,
                () => editor.chain().focus().toggleBlockquote().run(),
                editor.isActive("blockquote"),
              )}
              {tool(
                t("代码块"),
                Code,
                () => editor.chain().focus().toggleCodeBlock().run(),
                editor.isActive("codeBlock"),
              )}
              {tool(
                t("链接"),
                Link2,
                () => {
                  setInput(editor.getAttributes("link").href || "");
                  setDialog("link");
                },
                editor.isActive("link"),
              )}
              {tool(
                t("插入图片"),
                ImagePlus,
                () => file.current?.click(),
                false,
                busy,
              )}
              <Button
                disabled={readOnly || busy}
                onClick={() => {
                  setInput("");
                  setMathPosition(null);
                  setDialog("math");
                }}
              >
                {t("公式")}
              </Button>
              <Button
                disabled={readOnly || busy}
                onClick={() =>
                  editor
                    .chain()
                    .focus()
                    .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
                    .run()
                }
              >
                {t("插入表格")}
              </Button>
              {editor.isActive("table") && (
                <div className="note-table-tools">
                  <Button
                    disabled={readOnly || busy}
                    onClick={() => editor.chain().focus().addRowAfter().run()}
                  >
                    {t("添加行")}
                  </Button>
                  <Button
                    disabled={readOnly || busy}
                    onClick={() =>
                      editor.chain().focus().addColumnAfter().run()
                    }
                  >
                    {t("添加列")}
                  </Button>
                  <Button
                    disabled={readOnly || busy || !editor.can().mergeCells()}
                    onClick={() => editor.chain().focus().mergeCells().run()}
                  >
                    {t("合并单元格")}
                  </Button>
                  <Button
                    disabled={readOnly || busy || !editor.can().splitCell()}
                    onClick={() => editor.chain().focus().splitCell().run()}
                  >
                    {t("拆分单元格")}
                  </Button>
                  <Button
                    disabled={readOnly || busy}
                    onClick={() => editor.chain().focus().deleteRow().run()}
                  >
                    {t("删除行")}
                  </Button>
                  <Button
                    disabled={readOnly || busy}
                    onClick={() => editor.chain().focus().deleteColumn().run()}
                  >
                    {t("删除列")}
                  </Button>
                  <Button
                    disabled={readOnly || busy}
                    onClick={() => editor.chain().focus().deleteTable().run()}
                  >
                    {t("删除表格")}
                  </Button>
                </div>
              )}
            </div>
            <EditorContent editor={editor} className="note-document" />
          </>
        )
      )}
      <input
        ref={file}
        type="file"
        hidden
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => {
          if (e.target.files?.[0]) void upload(e.target.files[0]);
        }}
      />
      <Modal
        open={!!dialog}
        onOpenChange={() => setDialog(null)}
        title={
          dialog === "link"
            ? t("编辑链接")
            : mathPosition === null
              ? t("插入公式")
              : t("编辑公式")
        }
        description={
          dialog === "link"
            ? t("输入 HTTP(S) 链接；留空可移除链接。")
            : t("使用 LaTeX 语法输入公式。")
        }
      >
        <Field label={dialog === "link" ? t("链接地址") : t("LaTeX 公式")}>
          <input value={input} onChange={(e) => setInput(e.target.value)} />
        </Field>
        {dialog === "math" && (
          <label className="check-row">
            <input
              type="checkbox"
              checked={blockMath}
              disabled={mathPosition !== null}
              onChange={(e) => setBlockMath(e.target.checked)}
            />
            {t("独立公式块")}
          </label>
        )}
        <ErrorBox error={error} />
        <div className="modal-actions">
          <Button onClick={() => setDialog(null)}>{t("取消")}</Button>
          <Button
            variant="primary"
            onClick={() => {
              if (dialog === "link") {
                if (input && !/^https?:\/\//i.test(input)) {
                  setError(new Error(t("请输入有效的 HTTP(S) 链接。")));
                  return;
                }
                input
                  ? editor
                      ?.chain()
                      .focus()
                      .extendMarkRange("link")
                      .setLink({ href: input })
                      .run()
                  : editor?.chain().focus().unsetLink().run();
              } else if (input.trim() && mathPosition !== null) {
                if (blockMath)
                  editor
                    ?.chain()
                    .focus()
                    .updateBlockMath({ latex: input, pos: mathPosition })
                    .run();
                else
                  editor
                    ?.chain()
                    .focus()
                    .updateInlineMath({ latex: input, pos: mathPosition })
                    .run();
              } else if (input.trim()) {
                editor
                  ?.chain()
                  .focus()
                  .insertContent({
                    type: blockMath ? "blockMath" : "inlineMath",
                    attrs: { latex: input },
                  })
                  .run();
              }
              setDialog(null);
            }}
          >
            {t("确认")}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
