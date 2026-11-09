/* Live camera capture with getUserMedia; falls back to the phone's camera app via <input capture>. */
import { Camera, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "../../i18n";
import { Button } from "../ui";

export function CameraButton({ onFile }: { onFile: (file: File) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const fallbackInput = useRef<HTMLInputElement>(null);
  const supportsLive = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  return (
    <>
      <Button variant="secondary" onClick={() => (supportsLive ? setOpen(true) : fallbackInput.current?.click())} data-testid="camera-button">
        <Camera className="h-4 w-4" aria-hidden="true" />
        {t("upload.camera")}
      </Button>
      <input
        ref={fallbackInput}
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
      {open && (
        <CameraDialog
          onClose={() => setOpen(false)}
          onFile={(file) => {
            setOpen(false);
            onFile(file);
          }}
          onUnavailable={() => {
            setOpen(false);
            fallbackInput.current?.click();
          }}
        />
      )}
    </>
  );
}

function CameraDialog({ onClose, onFile, onUnavailable }: { onClose: () => void; onFile: (file: File) => void; onUnavailable: () => void }) {
  const { t } = useI18n();
  const video = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
      .then((media) => {
        active = media;
        setStream(media);
        if (video.current) video.current.srcObject = media;
      })
      .catch(() => setFailed(true));
    return () => active?.getTracks().forEach((track) => track.stop());
  }, []);

  function capture() {
    const element = video.current;
    if (!element || !element.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = element.videoWidth;
    canvas.height = element.videoHeight;
    canvas.getContext("2d")?.drawImage(element, 0, 0);
    canvas.toBlob((blob) => blob && onFile(new File([blob], "camera.jpg", { type: "image/jpeg" })), "image/jpeg", 0.92);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" role="dialog" aria-modal="true" aria-label={t("camera.title")}>
      <div className="w-full max-w-lg rounded-2xl bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-bold">{t("camera.title")}</h3>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-gray-100" aria-label={t("camera.cancel")}>
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        {failed ? (
          <div className="space-y-3">
            <p className="text-sm text-gray-700">{t("camera.denied")}</p>
            <Button onClick={onUnavailable}>{t("upload.choose")}</Button>
          </div>
        ) : (
          <>
            <video ref={video} autoPlay playsInline muted className="aspect-[3/4] w-full rounded-xl bg-black object-cover sm:aspect-video" />
            <div className="mt-3 flex justify-center gap-2">
              <Button onClick={capture} disabled={!stream}>
                <Camera className="h-4 w-4" aria-hidden="true" />
                {t("camera.capture")}
              </Button>
              <Button variant="ghost" onClick={onClose}>
                {t("camera.cancel")}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
