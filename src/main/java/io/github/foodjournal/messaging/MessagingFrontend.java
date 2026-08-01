package io.github.foodjournal.messaging;

import io.github.foodjournal.application.TransientVoicePayload;

/** A transport adapter. Provider identifiers and message identifiers are opaque strings. */
public interface MessagingFrontend {
  String provider();
  boolean enabled();
  int messageLimit();
  String send(String conversationId, String text);
  void edit(String conversationId, String messageId, String text);
  TransientVoicePayload download(Attachment attachment);
}
