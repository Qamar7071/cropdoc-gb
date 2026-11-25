/* Grad-CAM thumbnail + enlarged view with an opacity slider (heatmap layered over the model's view). */
import { ImageIcon, Maximize2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "../../i18n";
import { dataUrl } from "../../lib/files";

export function GradcamViewer({ overlay, heatmap, modelView }: { overlay: string; heatmap: string; modelView: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [opacity, setOpacity] = useState(55);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div>
      <h3 className="mb-3 flex items-center gap-2 text-base font-bold text-gray-900">
        <ImageIcon className="h-5 w-5 text-brand-700" aria-hidden="true" />
        {t("result.gradcam")}
      </h3>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group relative block w-full overflow-hidden rounded-xl"
        aria-label={t("result.enlarge")}
        data-testid="gradcam-thumb"
      >
        <img src={dataUrl(overlay, "image/png")} alt={t("result.gradcam")} className="aspect-[4/3] w-full object-cover" />
        <span className="absolute end-2 top-2 rounded-lg bg-black/50 p-1.5 text-white opacity-80 group-hover:opacity-100">
          <Maximize2 className="h-4 w-4" aria-hidden="true" />
        </span>
      </button>
      <p className="mt-1.5 text-xs text-gray-600">{t("result.gradcamHelp")}</p>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label={t("result.gradcam")}>
          <div className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-bold">{t("result.gradcam")}</h3>
              <button ref={closeRef} type="button" onClick={() => setOpen(false)} className="rounded-full p-2 hover:bg-gray-100" aria-label={t("result.close")}>
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="relative overflow-hidden rounded-xl">
              <img src={dataUrl(modelView, "image/jpeg")} alt={t("result.modelView")} className="block aspect-square w-full" />
              <img
                src={dataUrl(heatmap, "image/png")}
                alt=""
                className="absolute inset-0 block aspect-square w-full mix-blend-normal"
                style={{ opacity: opacity / 100 }}
              />
            </div>
            <label className="mt-4 block text-sm font-semibold text-gray-800">
              {t("result.opacity")}: <span dir="ltr" className="latin">{opacity}%</span>
              <input
                type="range"
                min={0}
                max={100}
                value={opacity}
                onChange={(event) => setOpacity(Number(event.target.value))}
                className="mt-2 block w-full accent-brand-700"
              />
            </label>
            <p className="mt-2 text-xs text-gray-600">{t("result.gradcamHelp")}</p>
          </div>
        </div>
      )}
    </div>
  );
}
