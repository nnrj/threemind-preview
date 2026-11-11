import { t } from "./i18n";
import { Field } from "./ui";
import type { Catalogue } from "./configuration";

export function kernelLabel(kernel: any): string {
  return (
    kernel.display_name || String(kernel.kernel_id).replace(/^threemind\./, "")
  );
}
export function KernelSelector({
  catalogue,
  value,
  onChange,
  disabled = false,
}: {
  catalogue: Catalogue;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const kernels = catalogue.kernels || [];
  const selected = kernels.find((kernel: any) => kernel.kernel_id === value);
  return (
    <section className="kernel-selection">
      <Field label={t("内核版本")}>
        <select
          aria-label={t("内核版本")}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {kernels.map((kernel: any) => (
            <option
              key={kernel.kernel_id}
              value={kernel.kernel_id}
              title={t(kernel.description || kernel.title)}
            >
              {kernelLabel(kernel)} · {t(kernel.description || kernel.title)}
            </option>
          ))}
        </select>
      </Field>
      {selected && (
        <p className="footnote">
          {t(selected.description || selected.title)}{" "}
          <code>{selected.kernel_id}</code>
        </p>
      )}
      {selected?.backends?.length === 1 &&
        selected.backends[0] === "reference" && (
          <p className="footnote">
            {t("此内核使用 Python 实现；不会替换为其他内核版本。")}
          </p>
        )}
      {value === "unified-associative" && (
        <p className="footnote">
          {t(
            "此历史内核采用自己的帧感官编码规则，文字节点编码由 sensory_encoding 设置。",
          )}
        </p>
      )}
    </section>
  );
}
