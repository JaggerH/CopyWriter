// Create ICO file from PNG
const { createCanvas, loadImage } = require('canvas');
const fs = require('fs');
const path = require('path');

// Simple ICO file creator (only supports single 256x256 image)
async function createIco() {
  const pngPath = path.join(__dirname, 'icon.png');
  const icoPath = path.join(__dirname, 'icon.ico');

  console.log('Creating ICO file from PNG...');

  // For simplicity, just copy the PNG to ICO for now
  // Electron-builder can handle PNG icons on Windows
  fs.copyFileSync(pngPath, icoPath);

  console.log('ICO file created:', icoPath);
}

createIco().catch(console.error);
