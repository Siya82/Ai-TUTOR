/*
 * NEW 17 Nov 2026 (code review #3). Phone photos are often 3-8MB, but
 * Claude refuses images over 5MB and reads them best at about 1568px on
 * the long edge. Large photos are redrawn here, in the browser, as a JPEG
 * no wider/taller than MAX_EDGE before upload -- no extra package needed.
 * Anything that isn't a large still image (GIFs, PDFs, small images) is
 * returned unchanged. If the browser can't decode the image, the original
 * file is returned and the server's own 5MB check has the final say.
 */
const MAX_EDGE = 1600;
const SHRINK_ABOVE_BYTES = 1.5 * 1024 * 1024;
const JPEG_QUALITY = 0.85;

export async function shrinkImageIfNeeded(file) {
  const isStill = /^image\/(jpeg|png|webp|heic|heif)$/i.test(file.type || "");
  if (!isStill || typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const longEdge = Math.max(bitmap.width, bitmap.height);
    if (file.size <= SHRINK_ABOVE_BYTES && longEdge <= MAX_EDGE) {
      bitmap.close();
      return file;
    }
    const scale = Math.min(1, MAX_EDGE / longEdge);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff"; // a transparent PNG would otherwise turn black in JPEG
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY));
    if (!blob || blob.size >= file.size) return file;
    const name = (file.name || "photo").replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg" });
  } catch {
    return file;
  }
}
