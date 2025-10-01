const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);
const os = require('os');

class AsrService {
  constructor(serviceUrl = 'http://localhost:8082') {
    this.serviceUrl = serviceUrl;
  }

  async convertWebMToWav(webmBuffer) {
    console.log('[ASR] Converting WebM to WAV...');

    // Create temp files
    const tmpDir = os.tmpdir();
    const timestamp = Date.now();
    const webmPath = path.join(tmpDir, `audio_${timestamp}.webm`);
    const wavPath = path.join(tmpDir, `audio_${timestamp}.wav`);

    try {
      // Write WebM buffer to temp file
      fs.writeFileSync(webmPath, webmBuffer);
      console.log(`[ASR] Wrote WebM to: ${webmPath}`);

      // Convert using FFmpeg
      const ffmpegCmd = `ffmpeg -i "${webmPath}" -ar 16000 -ac 1 -acodec pcm_s16le "${wavPath}" -y`;
      console.log(`[ASR] Running: ${ffmpegCmd}`);

      await execAsync(ffmpegCmd);
      console.log('[ASR] ✓ Conversion completed');

      // Read WAV file
      const wavBuffer = fs.readFileSync(wavPath);
      console.log(`[ASR] WAV size: ${wavBuffer.length} bytes`);

      // Cleanup temp files
      fs.unlinkSync(webmPath);
      fs.unlinkSync(wavPath);

      return wavBuffer;
    } catch (error) {
      // Cleanup on error
      if (fs.existsSync(webmPath)) fs.unlinkSync(webmPath);
      if (fs.existsSync(wavPath)) fs.unlinkSync(wavPath);
      throw error;
    }
  }

  async transcribe(audioBuffer) {
    try {
      console.log(`[ASR] Received audio buffer: ${audioBuffer.length} bytes`);

      // Convert WebM to WAV
      const wavBuffer = await this.convertWebMToWav(audioBuffer);

      const formData = new FormData();

      // Send as WAV file
      formData.append('file', wavBuffer, {
        filename: 'audio.wav',
        contentType: 'audio/wav'
      });

      console.log('[ASR] Sending WAV to ASR service...');

      const response = await axios.post(
        `${this.serviceUrl}/transcribe`,
        formData,
        {
          headers: {
            ...formData.getHeaders()
          },
          timeout: 30000 // 30 second timeout
        }
      );

      console.log('[ASR] ✓ Received response from ASR service');

      if (response.data && response.data.text) {
        console.log(`[ASR] Transcribed text: "${response.data.text}"`);
        return response.data.text;
      }

      console.log('[ASR] No text in response');
      return '';
    } catch (error) {
      console.error('[ASR] ✗ ASR service error:', error.message);
      if (error.response) {
        console.error('[ASR] Response data:', error.response.data);
      }
      throw error;
    }
  }

  async checkHealth() {
    try {
      const response = await axios.get(`${this.serviceUrl}/health`, {
        timeout: 5000
      });
      return response.status === 200;
    } catch (error) {
      return false;
    }
  }
}

module.exports = AsrService;