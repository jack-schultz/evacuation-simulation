import type { Space, Wall } from '../types/building';
import { SCALE, uid } from '../utils';

interface ComponentBox {
  minX: number; minY: number; maxX: number; maxY: number; count: number; touchesBorder: boolean;
}

function components(mask: Uint8Array, width: number, height: number, target: number): ComponentBox[] {
  const seen = new Uint8Array(mask.length);
  const queue = new Int32Array(mask.length);
  const found: ComponentBox[] = [];
  for (let start = 0; start < mask.length; start += 1) {
    if (seen[start] || mask[start] !== target) continue;
    let head = 0; let tail = 0;
    queue[tail++] = start; seen[start] = 1;
    const x0 = start % width; const y0 = Math.floor(start / width);
    const box: ComponentBox = { minX: x0, maxX: x0, minY: y0, maxY: y0, count: 0,
      touchesBorder: x0 === 0 || y0 === 0 || x0 === width - 1 || y0 === height - 1 };
    while (head < tail) {
      const index = queue[head++]; const x = index % width; const y = Math.floor(index / width);
      box.count += 1; box.minX = Math.min(box.minX, x); box.maxX = Math.max(box.maxX, x);
      box.minY = Math.min(box.minY, y); box.maxY = Math.max(box.maxY, y);
      box.touchesBorder ||= x === 0 || y === 0 || x === width - 1 || y === height - 1;
      const neighbors = [x > 0 ? index - 1 : -1, x + 1 < width ? index + 1 : -1,
        y > 0 ? index - width : -1, y + 1 < height ? index + width : -1];
      for (const next of neighbors) {
        if (next >= 0 && !seen[next] && mask[next] === target) {
          seen[next] = 1; queue[tail++] = next;
        }
      }
    }
    found.push(box);
  }
  return found;
}

export function detectFloorPlan(image: HTMLImageElement, worldWidth: number, worldHeight: number) {
  const scale = Math.min(384 / image.naturalWidth, 384 / image.naturalHeight);
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('Could not read the floor plan image');
  context.fillStyle = '#fff'; context.fillRect(0, 0, width, height);
  context.drawImage(image, 0, 0, width, height);
  const rgba = context.getImageData(0, 0, width, height).data;
  const mask = new Uint8Array(width * height);
  let blackPixels = 0;
  for (let i = 0; i < mask.length; i += 1) {
    const at = i * 4;
    const gray = 0.299 * rgba[at] + 0.587 * rgba[at + 1] + 0.114 * rgba[at + 2];
    mask[i] = gray < 128 ? 0 : 1;
    if (mask[i] === 0) blackPixels += 1;
  }
  if (blackPixels < mask.length * 0.005 || blackPixels > mask.length * 0.95) {
    throw new Error('Use a high contrast plan with a white background, black shapes, and clear room boundaries.');
  }

  const roomBoxes = components(mask, width, height, 1)
    .filter((b) => !b.touchesBorder && b.count >= Math.max(12, mask.length * 0.001));
  const obstacleBoxes = components(mask, width, height, 0).filter((b) => {
    const w = b.maxX - b.minX + 1; const h = b.maxY - b.minY + 1;
    return !b.touchesBorder && b.count >= Math.max(8, mask.length * 0.00008)
      && b.count / (w * h) >= 0.12 && w < width * 0.7 && h < height * 0.7;
  });
  const point = (x: number, y: number) => ({ x: x / width * worldWidth, y: y / height * worldHeight });
  const spaces: Space[] = roomBoxes.map((b, i) => {
    const a = point(b.minX, b.minY); const z = point(b.maxX + 1, b.maxY + 1);
    return { id: uid('room'), name: `Detected room ${i + 1}`, type: 'room', x: a.x, y: a.y,
      width: Math.max(z.x - a.x, 1 / SCALE), height: Math.max(z.y - a.y, 1 / SCALE), capacity_density_per_m2: null };
  });
  const walls: Wall[] = obstacleBoxes.map((b, i) => {
    const a = point(b.minX, b.minY); const z = point(b.maxX + 1, b.maxY + 1);
    return { id: uid('obstacle'), name: `Detected obstacle ${i + 1}`, x: a.x, y: a.y,
      width: Math.max(z.x - a.x, 1 / SCALE), height: Math.max(z.y - a.y, 1 / SCALE) };
  });
  const rows = Array.from({ length: height }, (_, y) => {
    let row = '';
    for (let x = 0; x < width; x += 1) row += mask[y * width + x] === 0 ? '1' : '0';
    return row;
  });
  return { spaces, walls, obstacle_map: { width, height, rows } };
}
