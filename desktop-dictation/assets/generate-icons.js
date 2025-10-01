// Script to generate icon from SVG using sharp or canvas
// For now, we'll create a simple PNG manually using node-canvas

const fs = require('fs');
const { createCanvas } = require('canvas');

function generateIcon(size, filename) {
  const canvas = createCanvas(size, size);
  const ctx = canvas.getContext('2d');

  // Background circle
  ctx.fillStyle = '#FF3B30';
  ctx.beginPath();
  ctx.arc(size/2, size/2, size*0.47, 0, Math.PI * 2);
  ctx.fill();

  // Microphone body (rounded rectangle)
  ctx.fillStyle = 'white';
  ctx.beginPath();
  const micWidth = size * 0.22;
  const micHeight = size * 0.31;
  const micX = size/2 - micWidth/2;
  const micY = size * 0.23;
  const radius = micWidth/2;

  ctx.moveTo(micX + radius, micY);
  ctx.lineTo(micX + micWidth - radius, micY);
  ctx.quadraticCurveTo(micX + micWidth, micY, micX + micWidth, micY + radius);
  ctx.lineTo(micX + micWidth, micY + micHeight - radius);
  ctx.quadraticCurveTo(micX + micWidth, micY + micHeight, micX + micWidth - radius, micY + micHeight);
  ctx.lineTo(micX + radius, micY + micHeight);
  ctx.quadraticCurveTo(micX, micY + micHeight, micX, micY + micHeight - radius);
  ctx.lineTo(micX, micY + radius);
  ctx.quadraticCurveTo(micX, micY, micX + radius, micY);
  ctx.fill();

  // Microphone stand
  ctx.strokeStyle = 'white';
  ctx.lineWidth = size * 0.047;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(size/2, micY + micHeight);
  ctx.lineTo(size/2, size * 0.70);
  ctx.stroke();

  // Microphone base
  ctx.beginPath();
  ctx.moveTo(size * 0.39, size * 0.70);
  ctx.lineTo(size * 0.61, size * 0.70);
  ctx.stroke();

  // Sound waves - left
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
  ctx.lineWidth = size * 0.031;
  ctx.beginPath();
  ctx.moveTo(size * 0.27, size * 0.35);
  ctx.quadraticCurveTo(size * 0.23, size * 0.35, size * 0.21, size * 0.39);
  ctx.stroke();

  // Sound waves - right
  ctx.beginPath();
  ctx.moveTo(size * 0.73, size * 0.35);
  ctx.quadraticCurveTo(size * 0.77, size * 0.35, size * 0.79, size * 0.39);
  ctx.stroke();

  // Sound waves - left outer
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
  ctx.beginPath();
  ctx.moveTo(size * 0.20, size * 0.43);
  ctx.quadraticCurveTo(size * 0.16, size * 0.43, size * 0.14, size * 0.49);
  ctx.stroke();

  // Sound waves - right outer
  ctx.beginPath();
  ctx.moveTo(size * 0.80, size * 0.43);
  ctx.quadraticCurveTo(size * 0.84, size * 0.43, size * 0.86, size * 0.49);
  ctx.stroke();

  // Save to file
  const buffer = canvas.toBuffer('image/png');
  fs.writeFileSync(filename, buffer);
  console.log(`Generated ${filename} (${size}x${size})`);
}

// Generate icons in multiple sizes
generateIcon(256, 'assets/icon.png');
generateIcon(128, 'assets/icon-128.png');
generateIcon(64, 'assets/icon-64.png');
generateIcon(32, 'assets/icon-32.png');
generateIcon(16, 'assets/icon-16.png');

console.log('All icons generated successfully!');
