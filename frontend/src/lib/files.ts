/* Client-side upload checks (the server checks again; never trust the client). */

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
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

export function dataUrl(base64: string, mime: string): string {
  return `data:${mime};base64,${base64}`;
}
