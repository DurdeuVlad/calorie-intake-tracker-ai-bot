package io.github.foodjournal.messaging;

import java.util.List;

/** The only message shape the journal processing pipeline accepts. */
public record InboundMessage(String provider, String eventId, String userId, String conversationId,
    String displayName, String languageCode, String text, String caption, List<Attachment> attachments) {
  public InboundMessage { attachments = attachments == null ? List.of() : List.copyOf(attachments); }
}
