package io.github.foodjournal.application;

public interface VoiceTranscriber { String transcribe(byte[] bytes, String mimeType); }
