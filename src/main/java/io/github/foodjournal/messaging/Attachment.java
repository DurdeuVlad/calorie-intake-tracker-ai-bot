package io.github.foodjournal.messaging;

/** Provider-neutral reference to media. Bytes are fetched only while processing. */
public record Attachment(Kind kind, String handle, String mimeType, String name) {
  public enum Kind { PHOTO, VOICE, DOCUMENT }
}
