import sharp from 'sharp';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = join(root, 'public');
const svg = readFileSync(join(publicDir, 'favicon.svg'));
const ogSvg = readFileSync(join(publicDir, 'og-image.svg'));

const sizes = [
  ['favicon-16.png', 16],
  ['favicon-32.png', 32],
  ['apple-touch-icon.png', 180],
  ['favicon-192.png', 192],
  ['favicon-512.png', 512],
];

for (const [name, width] of sizes) {
  await sharp(svg)
    .resize(width, width, { fit: 'cover' })
    .png()
    .toFile(join(publicDir, name));
  console.log(`wrote ${name}`);
}

await sharp(ogSvg).resize(1200, 630).png().toFile(join(publicDir, 'og-image.png'));
console.log('wrote og-image.png');

await sharp(svg).resize(32, 32).png().toFile(join(publicDir, 'favicon.ico'));
console.log('wrote favicon.ico');
