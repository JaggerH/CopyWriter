const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);
const os = require('os');
const logger = require('./logger');

class AsrService {
  constructor(serviceUrl = 'http://localhost:8082') {
    this.serviceUrl = serviceUrl;
  }

  async convertWebMToWav(webmBuffer) {
    logger.info('Converting WebM to WAV...');

    // Create temp files
    const tmpDir = os.tmpdir();
    const timestamp = Date.now();
    const webmPath = path.join(tmpDir, `audio_${timestamp}.webm`);
    const wavPath = path.join(tmpDir, `audio_${timestamp}.wav`);

    try {
      // Write WebM buffer to temp file
      fs.writeFileSync(webmPath, webmBuffer);
      logger.debug(`Wrote WebM to: ${webmPath}`);

      // Convert using FFmpeg
      const ffmpegCmd = `ffmpeg -i "${webmPath}" -ar 16000 -ac 1 -acodec pcm_s16le "${wavPath}" -y`;
      logger.debug(`Running FFmpeg: ${ffmpegCmd}`);

      await execAsync(ffmpegCmd);
      logger.info('FFmpeg conversion completed');

      // Read WAV file
      const wavBuffer = fs.readFileSync(wavPath);
      logger.debug(`WAV size: ${wavBuffer.length} bytes`);

      // Cleanup temp files
      fs.unlinkSync(webmPath);
      fs.unlinkSync(wavPath);

      return wavBuffer;
    } catch (error) {
      logger.error('FFmpeg conversion failed:', error.message);
      // Cleanup on error
      if (fs.existsSync(webmPath)) fs.unlinkSync(webmPath);
      if (fs.existsSync(wavPath)) fs.unlinkSync(wavPath);
      throw error;
    }
  }

  async transcribe(audioBuffer) {
    try {
      logger.info(`Received audio buffer: ${audioBuffer.length} bytes`);

      // Convert WebM to WAV
      const wavBuffer = await this.convertWebMToWav(audioBuffer);

      const formData = new FormData();

      // Send as WAV file
      formData.append('file', wavBuffer, {
        filename: 'audio.wav',
        contentType: 'audio/wav'
      });

      logger.info(`Sending WAV to ASR service: ${this.serviceUrl}/transcribe`);

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

      logger.info('Received response from ASR service');

      if (response.data && response.data.text) {
        logger.info(`Transcribed text: "${response.data.text}"`);
        return response.data.text;
      }

      logger.warn('No text in ASR response');
      return '';
    } catch (error) {
      logger.error('ASR service error:', error.message);
      if (error.response) {
        logger.error('ASR response data:', JSON.stringify(error.response.data));
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