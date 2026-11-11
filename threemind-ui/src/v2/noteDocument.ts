import { Editor, type JSONContent } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";
import { TableKit } from "@tiptap/extension-table";
import { TextStyleKit } from "@tiptap/extension-text-style";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import Image from "@tiptap/extension-image";
import { BlockMath, InlineMath } from "@tiptap/extension-mathematics";
import { TaskList, TaskItem } from "@tiptap/extension-list";
import { DOMSerializer } from "@tiptap/pm/model";
import { t } from "./i18n";

export const emptyDocument = (): JSONContent => ({
  type: "doc",
  content: [{ type: "paragraph" }],
});
export function noteExtensions(
  onMath?: (latex: string, position: number, block: boolean) => void,
) {
  return [
    StarterKit.configure({
      trailingNode: false,
      link: {
        openOnClick: false,
        HTMLAttributes: {
          rel: "noopener noreferrer nofollow",
          target: "_blank",
        },
      },
    }),
    Markdown.configure({ markedOptions: { gfm: true, breaks: false } }),
    TableKit.configure({ table: { resizable: true } }),
    TextStyleKit,
    TextAlign.configure({ types: ["heading", "paragraph"] }),
    Highlight.configure({ multicolor: true }),
    Image.configure({ allowBase64: false }),
    BlockMath.configure({
      katexOptions: {
        displayMode: true,
        throwOnError: false,
        trust: false,
        maxExpand: 1000,
      },
      onClick: onMath
        ? (node, pos) => onMath(node.attrs.latex, pos, true)
        : undefined,
    }),
    InlineMath.configure({
      katexOptions: {
        displayMode: false,
        throwOnError: false,
        trust: false,
        maxExpand: 1000,
      },
      onClick: onMath
        ? (node, pos) => onMath(node.attrs.latex, pos, false)
        : undefined,
    }),
    TaskList,
    TaskItem.configure({
      nested: true,
      a11y: {
        checkboxLabel: (node) =>
          t("任务：{text}", { text: node.textContent || t("空白任务") }),
      },
    }),
  ];
}

export function canonicalDocument(value: JSONContent): string {
  const cssKeys = new Set([
    "color",
    "backgroundColor",
    "fontFamily",
    "fontSize",
    "lineHeight",
    "textAlign",
  ]);
  const normalize = (item: any, key = ""): any => {
    if (Array.isArray(item)) return item.map((x) => normalize(x));
    if (item && typeof item === "object")
      return Object.fromEntries(
        Object.entries(item)
          .filter(([k, v]) => v != null && !(cssKeys.has(k) && v === ""))
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([k, v]) => [k, normalize(v, k)]),
      );
    if (
      typeof item === "string" &&
      ["color", "backgroundColor"].includes(key)
    ) {
      const span = document.createElement("span");
      span.style.color = item;
      return span.style.color || item;
    }
    return item;
  };
  return JSON.stringify(normalize(value));
}

export function toNoteMarkdown(
  editor: Editor,
  content: JSONContent = editor.getJSON(),
) {
  const canonical = (value: JSONContent) =>
    canonicalDocument(editor.schema.nodeFromJSON(value).toJSON());
  const plain = editor.markdown!.serialize(content);
  if (canonical(editor.markdown!.parse(plain)) === canonical(content))
    return { text: plain, extended: false };
  // Preserve rich attributes in readable HTML only where Markdown loses them.
  // The final roundtrip is checked before replacing any existing editor content.
  const serializer = DOMSerializer.fromSchema(editor.schema);
  let extended = false;
  const blocks = (content.content ?? []).map((block) => {
    const doc = { type: "doc", content: [block] };
    const markdown = editor.markdown!.serialize(doc);
    if (canonical(editor.markdown!.parse(markdown)) === canonical(doc))
      return markdown;
    const wrapper = document.createElement("div");
    wrapper.appendChild(
      serializer.serializeNode(editor.schema.nodeFromJSON(block)),
    );
    extended = true;
    return wrapper.innerHTML;
  });
  const text = blocks.join("\n\n");
  if (canonical(editor.markdown!.parse(text)) !== canonical(content)) {
    throw new Error(
      t("当前文档包含尚不能往返 Markdown 的格式，已保留当前文档。"),
    );
  }
  return { text, extended };
}

export function createNoteEditor(content: JSONContent = emptyDocument()) {
  return new Editor({ extensions: noteExtensions(), content });
}
