package io.github.foodjournal.application;

import java.util.Arrays;

/** A short-lived voice payload. Closing it erases its backing bytes. */
public final class TransientVoicePayload implements AutoCloseable {
  private final byte[] bytes;

  public TransientVoicePayload(byte[] bytes) {
    this.bytes = bytes;
  }

  public byte[] bytes() {
    return bytes;
  }

  @Override
  public void close() {
    if (bytes != null) Arrays.fill(bytes, (byte) 0);
  }
}
