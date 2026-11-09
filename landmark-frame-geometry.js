// Recognize exact, symmetric, uniform video padding from pixels alone. Never
// infer a word/person ROI or discard a tracking result. Real camera texture
// and noisy backgrounds do not satisfy the exact uniform-padding checks.
export function uniformPaddingRect({width, height, data}) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 8 || height < 8
    || !data || data.length !== width * height * 4) return null;
  const color = Array.from(data.slice(0, 4));
  if (color[3] !== 255) return null;
  const same = (x, y) => color.every((c, i) => data[(y * width + x) * 4 + i] === c);
  const column = x => {for (let y = 0; y < height; y++) if (!same(x, y)) return false;return true;};
  const row = y => {for (let x = 0; x < width; x++) if (!same(x, y)) return false;return true;};
  let left = 0, right = 0, top = 0, bottom = 0;
  while (left < width && column(left)) left++;
  while (right < width && column(width - right - 1)) right++;
  while (top < height && row(top)) top++;
  while (bottom < height && row(height - bottom - 1)) bottom++;
  const horizontal = left >= 2 && right >= 2 && Math.abs(left - right) <= 1
    && !top && !bottom && left + right <= width * .5;
  const vertical = top >= 2 && bottom >= 2 && Math.abs(top - bottom) <= 1
    && !left && !right && top + bottom <= height * .5;
  if (!horizontal && !vertical) return null;
  // Retain an extra preview-pixel border rather than risk cutting into an
  // antialiased source edge. An all-blank image never supplies a crop.
  left = horizontal ? left - 1 : 0;right = horizontal ? right - 1 : 0;
  top = vertical ? top - 1 : 0;bottom = vertical ? bottom - 1 : 0;
  return {x: left / width, y: top / height,
    width: 1 - (left + right) / width, height: 1 - (top + bottom) / height};
}

export function restoreTrackingCoordinates(result, crop, width, height) {
  if (!crop) return result;
  const restore = points => Array.isArray(points) ? points.map(p => ({...p,
    x: (crop.x + p.x * crop.width) / width,
    y: (crop.y + p.y * crop.height) / height,
    z: (p.z ?? 0) * crop.width / width})) : points;
  return {...result, poseLandmarks: restore(result.poseLandmarks),
    leftHandLandmarks: restore(result.leftHandLandmarks),
    rightHandLandmarks: restore(result.rightHandLandmarks)};
}

export function trackingSnapshot(video, createCanvas = () => document.createElement('canvas')) {
  const width = video.videoWidth, height = video.videoHeight;
  if (!width || !height) throw new Error('Camera image dimensions are unavailable.');
  const preview = createCanvas();
  preview.width = 64;preview.height = Math.max(8, Math.round(64 * height / width));
  const pixels = preview.getContext('2d', {alpha: false, willReadFrequently: true});
  let rect = null;
  try {
    if (pixels) {
      pixels.drawImage(video, 0, 0, preview.width, preview.height);
      rect = uniformPaddingRect(pixels.getImageData(0, 0, preview.width, preview.height));
    }
  } catch {
    // Pixel inspection is optional: cross-origin/unsupported reads must not
    // disable otherwise usable full-frame camera tracking.
  } finally {preview.width = 0;preview.height = 0;}
  const crop = rect ? {x: rect.x * width, y: rect.y * height,
    width: rect.width * width, height: rect.height * height} : null;
  const view = crop || {x: 0, y: 0, width, height};
  const scale = Math.min(1, 640 / Math.max(view.width, view.height));
  const canvas = createCanvas();
  canvas.width = Math.max(1, Math.round(view.width * scale));
  canvas.height = Math.max(1, Math.round(view.height * scale));
  const context = canvas.getContext('2d', {alpha: false});
  try {
    if (!context) throw new Error('Camera frame buffering is unavailable.');
    context.drawImage(video, view.x, view.y, view.width, view.height, 0, 0, canvas.width, canvas.height);
  } catch (error) {canvas.width = 0;canvas.height = 0;throw error;}
  return {image: canvas, dimensions: [canvas.width, canvas.height], cropped: Boolean(crop),
    sourceDimensions: [width, height],
    restore: result => restoreTrackingCoordinates(result, crop, width, height),
    dispose: () => {canvas.width = 0;canvas.height = 0;}};
}
