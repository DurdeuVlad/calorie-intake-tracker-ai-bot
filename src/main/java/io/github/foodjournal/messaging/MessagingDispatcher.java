package io.github.foodjournal.messaging;

import io.github.foodjournal.domain.MessagingOutboundMessage;
import io.github.foodjournal.repository.MessagingOutboundRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MessagingDispatcher {
  private static final Logger log = LoggerFactory.getLogger(MessagingDispatcher.class);
  private final MessagingOutboundRepository messages;
  private final FrontendRegistry frontends;

  public MessagingDispatcher(MessagingOutboundRepository messages, FrontendRegistry frontends) {
    this.messages = messages;
    this.frontends = frontends;
  }

  @Scheduled(fixedDelayString = "${food-journal.outbox-delay-ms:5000}")
  public void dispatch() {
    List<MessagingOutboundMessage> ready = messages.lockReady();
    for (MessagingOutboundMessage message : ready) {
      processSingle(message);
    }
  }

  private void processSingle(MessagingOutboundMessage message) {
    message.claim();
    messages.save(message);
    try {
      MessagingFrontend frontend = frontends.require(message.getProvider());
      String text = fit(message.getText(), frontend.messageLimit());
      frontend.send(message.getConversationId(), text);
      message.sent();
      messages.save(message);
    } catch (Exception failure) {
      log.error("Failed to send outbound message id={}: {}", message.getId(), failure.getMessage(), failure);
      message.retry();
      messages.save(message);
    }
  }

  static String fit(String text, int limit) {
    if (text == null) return "";
    if (text.length() <= limit) return text;
    String suffix = "\n[Message truncated]";
    if (limit <= suffix.length()) return suffix.substring(0, limit);
    return text.substring(0, limit - suffix.length()) + suffix;
  }
}
