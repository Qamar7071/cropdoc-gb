/* Upload Leaf Image card: drag & drop, Choose File, Camera, Analyze, crop hint, save toggle, Quick Examples. */
import { useQuery } from "@tanstack/react-query";
import { CloudUpload, FolderOpen, Leaf, RefreshCw, ScanSearch } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { useI18n } from "../../i18n";
import { api } from "../../lib/api";
import { checkFile } from "../../lib/files";
import { Button, Card, CardTitle, IconBubble } from "../ui";
import { CameraButton } from "./CameraCapture";

interface Example {
  id: string;
  file: string;
  class_id: string;
  label_key: string;
}

interface Props {
  file: File | null;
  previewUrl: string | null;
  busy: boolean;
  cropHint: string;
  save: boolean;
  onFile: (file: File) => void;
  onCropHint: (crop: string) => void;
  onSave: (save: boolean) => void;
  onAnalyze: (file?: File) => void;
}

export function UploadCard({ file, previewUrl, busy, cropHint, save, onFile, onCropHint, onSave, onAnalyze }: Props) {
  const { t, crop } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  const examples = useQuery({
    queryKey: ["examples"],
    queryFn: async () => (await (await fetch("/examples/examples.json")).json()) as { examples: Example[] },
    staleTime: Infinity,
  });

  function accept(candidate: File | undefined, analyze = false) {
    if (!candidate) return;
    const issue = checkFile(candidate);
    if (issue) {
      setProblem(issue === "type" ? t("upload.errorType") : t("upload.errorSize"));
      return;
    }
    setProblem(null);
    onFile(candidate);
    if (analyze) onAnalyze(candidate);
  }

  async function loadExample(example: Example) {
    const blob = await (await fetch(example.file)).blob();
    accept(new File([blob], `${example.id}.jpg`, { type: "image/jpeg" }), true);
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files?.[0]);
  };

  return (
    <Card data-testid="upload-card">
      <CardTitle
        icon={
          <IconBubble>
            <CloudUpload className="h-6 w-6" />
          </IconBubble>
        }
        title={t("upload.title")}
        subtitle={t("upload.subtitle")}
      />

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`rounded-xl border-2 border-dashed p-5 text-center transition-colors sm:p-6 ${dragging ? "border-brand-600 bg-brand-100" : "border-brand-500/60 bg-brand-50/60"}`}
        data-testid="dropzone"
      >
        {previewUrl ? (
          <img src={previewUrl} alt={t("upload.preview")} className="mx-auto max-h-72 rounded-xl object-contain shadow-sm" />
        ) : (
          <button
            type="button"
            onClick={() => input.current?.click()}
            className="mx-auto flex w-full flex-col items-center rounded-lg py-4"
            aria-label={t("upload.dropzoneLabel")}
          >
            <CloudUpload className="h-16 w-16 text-brand-700" strokeWidth={1.6} aria-hidden="true" />
            <span className="mt-2 text-xl font-semibold text-gray-900">{t("upload.drop")}</span>
            <span className="mt-1 text-sm text-gray-600">{t("upload.or")}</span>
          </button>
        )}
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          {previewUrl ? (
            <>
              <Button variant="secondary" onClick={() => input.current?.click()}>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {t("upload.change")}
              </Button>
              <CameraButton onFile={(captured) => accept(captured)} />
              <Button variant="accent" onClick={() => onAnalyze()} disabled={!file || busy} data-testid="analyze-button">
                <ScanSearch className="h-4 w-4" aria-hidden="true" />
                {t("upload.analyze")}
              </Button>
            </>
          ) : (
            <>
              <Button onClick={() => input.current?.click()} className="px-7 py-3 text-base" data-testid="choose-file">
                <FolderOpen className="h-5 w-5" aria-hidden="true" />
                {t("upload.choose")}
              </Button>
              <CameraButton onFile={(captured) => accept(captured)} />
            </>
          )}
        </div>
        <p className="mt-3 text-[13px] text-gray-600">{t("upload.formats")}</p>
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png"
          className="hidden"
          data-testid="file-input"
          onChange={(event) => {
            accept(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </div>

      {problem && (
        <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-800" data-testid="upload-error">
          {problem}
        </p>
      )}

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex flex-1 items-center gap-2 text-sm font-semibold text-gray-800">
          <span className="shrink-0">{t("upload.cropHint")}</span>
          <select
            value={cropHint}
            onChange={(event) => onCropHint(event.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 font-normal"
            data-testid="crop-hint"
          >
            <option value="">{t("upload.cropAny")}</option>
            {(model.data?.crops ?? []).map((name) => (
              <option key={name} value={name}>
                {crop(name)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-gray-800">
          <input
            type="checkbox"
            checked={save}
            onChange={(event) => onSave(event.target.checked)}
            className="h-5 w-5 rounded accent-brand-700"
            data-testid="save-toggle"
          />
          {t("upload.save")}
        </label>
      </div>

      <div className="mt-6">
        <h3 className="mb-3 flex items-center gap-2 text-base font-bold text-gray-900">
          <Leaf className="h-5 w-5 text-brand-700" aria-hidden="true" />
          {t("upload.quickExamples")}
        </h3>
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(examples.data?.examples ?? []).map((example) => (
            <li key={example.id}>
              <button
                type="button"
                onClick={() => loadExample(example)}
                disabled={busy}
                className="group w-full text-center"
                data-testid={`example-${example.id}`}
              >
                <img
                  src={example.file}
                  alt={t(example.label_key)}
                  className="aspect-[4/3] w-full rounded-xl object-cover shadow-sm transition group-hover:ring-4 group-hover:ring-brand-200"
                />
                <span className="mt-2 block text-[15px] font-semibold text-gray-900">{t(example.label_key)}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-gray-500">{t("upload.examplesNote")}</p>
      </div>
    </Card>
  );
}
