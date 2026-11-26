/* Client-side upload checks (the server checks again; never trust the client). */

/** Largest photo the user may pick. Bigger phone photos are shrunk in the browser before upload. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
/** Photos above this are shrunk first: the server accepts 5 MB, some hosts (Vercel) only 4.5 MB per request. */
export const SEND_AS_IS_BYTES = 3.5 * 1024 * 1024;
const MAX_SIDE = 2048; // far more than the model needs (it looks at 224 x 224) and enough for history
const ALLOWED_TYPES = ["image/jpeg", "image/png"];
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png"];

export type FileProblem = "type" | "size" | null;

export function checkFile(file: File): FileProblem {
  const name = file.name.toLowerCase();
  const typeOk = ALLOWED_TYPES.includes(file.type) || ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!typeOk) return "type";
  if (file.size > MAX_UPLOAD_BYTES) return "size";
  return null;
}

/**
 * Make a photo small enough to upload quickly on mobile data and within every host's request limit.
 * Small photos are sent unchanged. Large ones are redrawn at most 2048 px on the long side as JPEG
 * (the phone's rotation is applied, and the redraw drops GPS/EXIF data as a bonus).
 * If the browser cannot decode the photo here, the original is sent and the server decides.
 */
export async function prepareUpload(file: File): Promise<File> {
  if (file.size <= SEND_AS_IS_BYTES || typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    for (const quality of [0.9, 0.8, 0.7]) {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      if (blob && blob.size <= SEND_AS_IS_BYTES) {
        return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
      }
    }
  } catch {
    /* fall through: send the original */
  }
  return file;
}

export function dataUrl(base64: string, mime: string): string {
  return `data:${mime};base64,${base64}`;
}
