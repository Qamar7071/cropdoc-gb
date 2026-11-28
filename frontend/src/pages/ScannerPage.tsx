import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { Hero } from "../components/Hero";
import { HowItWorksCard, RecentStatsCard } from "../components/InfoCards";
import { ResultCard } from "../components/result/ResultCard";
import { UploadCard } from "../components/upload/UploadCard";
import { useI18n } from "../i18n";
import { api, type PredictResponse } from "../lib/api";
import { prepareUpload } from "../lib/files";
import { useDistrict } from "../state/district";
import { lastScan } from "../state/lastScan";

export function ScannerPage() {
  const { t } = useI18n();
  const { district } = useDistrict();
  const queryClient = useQueryClient();
  // start from the last scan of this visit (e.g. coming back from the treatment guide)
  const [file, setFile] = useState<File | null>(() => lastScan.file);
  const [cropHint, setCropHint] = useState(() => lastScan.cropHint);
  const [save, setSave] = useState(true);
  const [result, setResult] = useState<PredictResponse | null>(() => lastScan.result);
  const restored = useRef(lastScan.result !== null);

  useEffect(() => {
    lastScan.file = file;
    lastScan.result = result;
    lastScan.cropHint = cropHint;
  }, [file, result, cropHint]);

  useEffect(() => {
    // on phones the report sits below the photo: show it again straight away when coming back
    if (restored.current && window.matchMedia("(max-width: 1279px)").matches) {
      document.querySelector('[data-testid="result-card"]')?.scrollIntoView({ block: "start" });
    }
  }, []);

  // preview URL derived from the file; released when the file changes or the page unmounts
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const mutation = useMutation({
    mutationFn: async (vars: { file: File; save: boolean }) =>
      api.predict(await prepareUpload(vars.file), { cropHint: cropHint || undefined, district: district || undefined, save: vars.save }),
    onSuccess: (data) => {
      setResult(data);
      if (data.saved) {
        queryClient.invalidateQueries({ queryKey: ["scans"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
      }
    },
  });

  const analyze = (candidate?: File) => {
    const target = candidate ?? file;
    if (!target) return;
    setResult(null);
    mutation.mutate({ file: target, save });
  };

  return (
    <div className="page-backdrop">
      <Hero />
      <div className="mx-auto max-w-[1480px] px-4 pb-6 lg:px-6">
        <h2 className="sr-only">{t("nav.scanner")}</h2>
        {/* phone/tablet order: upload, result, info. Desktop: upload + info on the left, result on the right */}
        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
          <div className="xl:col-start-1 xl:row-start-1">
            <UploadCard
            file={file}
            previewUrl={previewUrl}
            busy={mutation.isPending}
            cropHint={cropHint}
            save={save}
            onFile={(next) => {
              setFile(next);
              setResult(null);
              mutation.reset();
            }}
            onCropHint={setCropHint}
            onSave={setSave}
            onAnalyze={analyze}
            />
          </div>
          <div className="xl:col-start-2 xl:row-span-2 xl:row-start-1">
            <ResultCard
              result={result}
              previewUrl={previewUrl}
              loading={mutation.isPending}
              error={mutation.error}
              saving={mutation.isPending}
              onSave={file ? () => mutation.mutate({ file, save: true }) : undefined}
              onReset={() => {
                setFile(null);
                setResult(null);
                mutation.reset();
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          </div>
          <div className="no-print grid gap-5 lg:grid-cols-2 xl:col-start-1 xl:row-start-2 xl:grid-cols-1">
            <HowItWorksCard />
            <RecentStatsCard />
          </div>
        </div>
      </div>
    </div>
  );
}
