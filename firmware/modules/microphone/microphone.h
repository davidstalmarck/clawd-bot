/**
 * @file microphone.h
 * @brief I2S MEMS Microphone Module (ICS-43434) for Athera
 *
 * I2S digital microphone for capturing audio and measuring sound levels.
 * Audio capture runs in a background FreeRTOS task so the main loop stays responsive.
 * Double module spanning two adjacent ports.
 *
 * Specifications:
 * - Interface: I2S (3 signal pins + L/R select)
 * - Microphone: ICS-43434 MEMS
 * - Sample Rate: 16000 Hz
 * - Bit Depth: 24-bit (left-aligned in 32-bit frame)
 * - SNR: 65 dBA
 * - Max recording: ~10 seconds (320KB heap)
 *
 * Athera Connector (double module):
 * - Port 1 Line A: LR (left/right channel select, LOW=left, HIGH=right)
 * - Port 1 Line B: WS (word select / LRCLK)
 * - Port 2 Line A: SCK (serial clock / BCLK)
 * - Port 2 Line B: SD (serial data)
 */

#ifndef MICROPHONE_MODULE_H
#define MICROPHONE_MODULE_H

#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

class Microphone {
public:
    static constexpr int SAMPLE_RATE = 16000;
    static constexpr int BUFFER_SAMPLES = 512;
    static constexpr int MAX_RECORD_SECONDS = 3;
    static constexpr int MAX_RECORD_SAMPLES = SAMPLE_RATE * MAX_RECORD_SECONDS;
    static constexpr int STREAM_SAMPLES = 8192;   // streaming ring, ~0.5 s

    /**
     * @brief Construct Microphone module
     * @param lrPin   L/R channel select pin (Line A of primary port)
     * @param wsPin   I2S word select pin (Line B of primary port)
     * @param sckPin  I2S serial clock pin (Line A of secondary port)
     * @param sdPin   I2S serial data pin (Line B of secondary port)
     */
    Microphone(int lrPin, int wsPin, int sckPin, int sdPin);

    /**
     * @brief Initialize I2S driver and start background capture task
     */
    void begin();

    /**
     * @brief Get current sound level (RMS amplitude)
     * @return RMS value from 0 to 32767
     */
    int16_t getSoundLevel();

    /**
     * @brief Check if sound level exceeds a threshold
     * @param threshold RMS threshold (0-32767)
     * @return true if current sound level exceeds threshold
     */
    bool isSoundDetected(int16_t threshold = 500);

    /**
     * @brief Get peak amplitude since last call
     * @return Peak value from 0 to 32767 (resets after read)
     */
    int16_t getPeakAmplitude();

    /**
     * @brief Copy latest audio samples into a user buffer
     * @param dest Destination buffer (must hold at least numSamples int16_t)
     * @param numSamples Number of samples to copy (max BUFFER_SAMPLES)
     * @return Number of samples actually copied
     */
    int getSamples(int16_t* dest, int numSamples);

    /**
     * @brief Start recording audio into heap buffer
     * Records up to MAX_RECORD_SECONDS (10s) of audio.
     */
    void startRecording();

    /**
     * @brief Stop recording
     */
    void stopRecording();

    /**
     * @brief Check if currently recording
     * @return true if recording is in progress
     */
    bool isRecording();

    /**
     * @brief Get pointer to recorded audio buffer
     * @return Pointer to 16-bit mono samples, or nullptr if no recording
     */
    const int16_t* getRecording();

    /**
     * @brief Get number of recorded samples
     * @return Sample count (divide by SAMPLE_RATE to get duration in seconds)
     */
    int getRecordingLength();

    /**
     * @brief Start continuous streaming into a ring buffer (no length cap).
     * Unlike getSamples() (a snapshot of the latest block), every captured
     * sample is delivered exactly once via readStream(). Allocates 16 KB on
     * first call. Drain at least every ~250 ms or samples are dropped.
     */
    void startStream();

    /** @brief Stop streaming. Unread samples are discarded. */
    void stopStream();

    /**
     * @brief Copy up to maxSamples unread streamed samples into dest.
     * @return Number of samples copied (0 if nothing new or not streaming)
     */
    int readStream(int16_t* dest, int maxSamples);

    /** @brief Samples dropped because the ring was full since startStream(). */
    uint32_t streamOverruns();

    /**
     * @brief Set L/R channel selection
     * @param right true = right channel (LR pin HIGH), false = left channel (LR pin LOW)
     */
    void setChannel(bool right);

    // Background task function (public for static callback, do not call directly)
    void _captureTaskLoop();

private:
    int _lrPin;
    int _wsPin;
    int _sckPin;
    int _sdPin;
    bool _initialized;

    volatile int16_t _rmsLevel;
    volatile int16_t _peakLevel;

    int16_t _sampleBuffer[BUFFER_SAMPLES];
    volatile int _sampleCount;

    // Recording state
    int16_t* _recordBuffer;          // Heap-allocated recording buffer
    volatile int _recordLength;       // Samples recorded so far
    volatile bool _recording;

    // Streaming ring (single producer: capture task, single consumer: loop)
    int16_t* _streamBuffer;
    volatile uint32_t _streamHead;    // written by capture task
    volatile uint32_t _streamTail;    // written by readStream()
    volatile bool _streaming;
    volatile uint32_t _streamOverruns;

    TaskHandle_t _captureTask;
};

#endif // MICROPHONE_MODULE_H
