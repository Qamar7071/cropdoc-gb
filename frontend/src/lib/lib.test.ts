import { checkFile, MAX_UPLOAD_BYTES } from "./files";
import { percent } from "./format";

test("client-side upload checks: type and 5 MB limit", () => {
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
