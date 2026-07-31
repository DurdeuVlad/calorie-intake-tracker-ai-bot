package io.github.foodjournal.application;

/** Provider-specific transcription of already-downloaded, transient voice bytes. */
public interface VoiceTranscriptionProvider {
  String name();
  String transcribe(byte[] bytes, String mimeType);
}
