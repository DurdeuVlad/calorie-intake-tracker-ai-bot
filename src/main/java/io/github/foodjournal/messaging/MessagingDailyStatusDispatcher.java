package io.github.foodjournal.messaging;

import io.github.foodjournal.domain.MessagingDailyStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class MessagingDailyStatusDispatcher {
  private static final Logger log = LoggerFactory.getLogger(MessagingDailyStatusDispatcher.class);
  private final MessagingDailyStatusService statuses;
  private final FrontendRegistry frontends;

  public MessagingDailyStatusDispatcher(MessagingDailyStatusService statuses, FrontendRegistry frontends) {
    this.statuses = statuses;
    this.frontends = frontends;
  }

  @Scheduled(fixedDelayString = "${food-journal.outbox-delay-ms:5000}")
  public void dispatch() {
    MessagingDailyStatus status = statuses.claim();
    if (status == null) return;
    try {
      MessagingFrontend frontend = frontends.require(status.getProvider());
      String id = status.getRemoteMessageId();
      if (id == null) {
        status.delivered(frontend.send(status.getConversationId(), MessagingDispatcher.fit(status.getText(), frontend.messageLimit())));
      } else {
        frontend.edit(status.getConversationId(), id, MessagingDispatcher.fit(status.getText(), frontend.messageLimit()));
        status.delivered(id);
      }
    } catch (Exception e) {
      log.error("Failed to dispatch daily status: {}", e.getMessage());
    }
  }
}
