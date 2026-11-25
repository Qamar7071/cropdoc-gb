/* Camera access for the live scanner: back camera first, switch camera, flashlight where supported. */
import { useCallback, useEffect, useRef, useState } from "react";

export type CameraProblem = "insecure" | "unsupported" | "denied" | "not_found" | "busy" | "other";

export interface CameraState {
  stream: MediaStream | null;
  starting: boolean;
  problem: CameraProblem | null;
  canSwitch: boolean;
  torchSupported: boolean;
  torchOn: boolean;
  facing: "environment" | "user";
}

type TorchCapabilities = MediaTrackCapabilities & { torch?: boolean };

export function cameraProblemOf(error: unknown): CameraProblem {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "not_found";
  if (name === "NotReadableError" || name === "AbortError") return "busy";
  return "other";
}

function environmentProblem(): CameraProblem | null {
  if (typeof window === "undefined") return "unsupported";
  if (!window.isSecureContext) return "insecure";
  if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
  return null;
}

interface Opened {
  stream: MediaStream;
  canSwitch: boolean;
  torchSupported: boolean;
  facing: "environment" | "user";
}

export function useCamera(video: React.RefObject<HTMLVideoElement | null>, active: boolean) {
  const [opened, setOpened] = useState<Opened | null>(null);
  const [failure, setFailure] = useState<{ key: string; problem: CameraProblem } | null>(null);
  const [torch, setTorch] = useState<{ on: boolean; broken: boolean }>({ on: false, broken: false });
  const streamRef = useRef<MediaStream | null>(null);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [attempt, setAttempt] = useState(0);
  const envProblem = environmentProblem();
  const requestKey = `${facing}:${attempt}`;

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    if (!active || envProblem) {
      stop();
      return;
    }
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({
        audio: false,
        video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 720 } },
      })
      .then(async (media) => {
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stop();
        streamRef.current = media;
        if (video.current) {
          video.current.srcObject = media;
          await video.current.play().catch(() => undefined);
        }
        const track = media.getVideoTracks()[0];
        const capabilities = (track?.getCapabilities?.() ?? {}) as TorchCapabilities;
        const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
        if (cancelled) return;
        setTorch({ on: false, broken: false });
        setFailure(null);
        setOpened({
          stream: media,
          canSwitch: devices.filter((d) => d.kind === "videoinput").length > 1,
          torchSupported: capabilities.torch === true,
          facing,
        });
      })
      .catch((error: unknown) => {
        if (!cancelled) setFailure({ key: requestKey, problem: cameraProblemOf(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [active, envProblem, facing, requestKey, stop, video]);

  // always release the camera when leaving the page
  useEffect(() => stop, [stop]);

  const switchCamera = useCallback(() => setFacing((f) => (f === "environment" ? "user" : "environment")), []);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const toggleTorch = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    const next = !torch.on;
    try {
      await track.applyConstraints({ advanced: [{ torch: next } as MediaTrackConstraintSet] });
      setTorch({ on: next, broken: false });
    } catch {
      setTorch({ on: false, broken: true });
    }
  }, [torch.on]);

  // everything below is derived, so switching pages/cameras never leaves stale state behind
  const live = active && opened !== null && opened.stream.active && opened.facing === facing;
  const problem: CameraProblem | null = envProblem ?? (failure?.key === requestKey ? failure.problem : null);
  const state: CameraState = {
    stream: live ? opened.stream : null,
    starting: active && !problem && !live,
    problem: active ? problem : null,
    canSwitch: opened?.canSwitch ?? false,
    torchSupported: live && opened.torchSupported && !torch.broken,
    torchOn: live && torch.on,
    facing,
  };
  return { ...state, switchCamera, toggleTorch, retry };
}
