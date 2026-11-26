import { checkFile, MAX_UPLOAD_BYTES, prepareUpload, SEND_AS_IS_BYTES } from "./files";
import { percent } from "./format";

test("client-side upload checks: type and 25 MB limit", () => {
  expect(checkFile(new File(["x"], "leaf.jpg", { type: "image/jpeg" }))).toBeNull();
  expect(checkFile(new File(["x"], "leaf.png", { type: "image/png" }))).toBeNull();
  expect(checkFile(new File(["x"], "leaf.gif", { type: "image/gif" }))).toBe("type");
  expect(checkFile(new File(["x"], "notes.txt", { type: "text/plain" }))).toBe("type");
  const big = new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], "big.jpg", { type: "image/jpeg" });
  expect(checkFile(big)).toBe("size");
});

test("percent never invents a number", () => {
  expect(percent(null)).toBe("—");
  expect(percent(undefined)).toBe("—");
  expect(percent(0.9645)).toBe("96.5%");
});

test("prepareUpload sends small photos unchanged and never fails on large ones", async () => {
  const small = new File(["x"], "leaf.jpg", { type: "image/jpeg" });
  expect(await prepareUpload(small)).toBe(small);
  // jsdom cannot decode images: the original is sent and the server decides (no crash, no lost photo)
  const large = new File([new Uint8Array(SEND_AS_IS_BYTES + 1)], "phone.jpg", { type: "image/jpeg" });
  expect(await prepareUpload(large)).toBe(large);
  // phone photos up to 25 MB may be picked; they are shrunk before upload
  expect(checkFile(new File([new Uint8Array(8 * 1024 * 1024)], "phone.jpg", { type: "image/jpeg" }))).toBeNull();
});
