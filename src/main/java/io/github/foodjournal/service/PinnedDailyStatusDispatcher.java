package io.github.foodjournal.service;

import io.github.foodjournal.application.DailyStatusService;
import io.github.foodjournal.repository.PinnedDailyStatusRepository;
import io.github.foodjournal.telegram.TelegramGateway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
@ConditionalOnProperty(prefix = "food-journal", name = "scheduling-enabled", havingValue = "true", matchIfMissing = true)
public class PinnedDailyStatusDispatcher {
  private static final Logger log = LoggerFactory.getLogger(PinnedDailyStatusDispatcher.class);
  private final PinnedDailyStatusRepository statuses;
  private final DailyStatusService statusService;
  private final TelegramGateway telegram;

  public PinnedDailyStatusDispatcher(PinnedDailyStatusRepository s, DailyStatusService d, TelegramGateway t) {
    this.statuses = s;
    this.statusService = d;
    this.telegram = t;
  }

  @Scheduled(fixedDelayString = "${food-journal.outbox-delay-ms:5000}")
  public void dispatch() {
    DailyStatusService.Delivery status = statusService.claim();
    if (status == null) return;
    Long messageId = status.messageId();
    try {
      if (messageId == null) {
        messageId = telegram.sendMessage(status.chatId(), status.text());
        statusService.rememberMessage(status.id(), status.leaseToken(), messageId);
      } else {
        try {
          telegram.editMessage(status.chatId(), messageId, status.text());
        } catch (Exception editError) {
          log.warn("Failed to edit pinned message {}, sending new message: {}", messageId, editError.getMessage());
          messageId = telegram.sendMessage(status.chatId(), status.text());
          statusService.rememberMessage(status.id(), status.leaseToken(), messageId);
        }
      }
      try {
        telegram.pinMessage(status.chatId(), messageId);
      } catch (Exception pinError) {
        log.warn("Failed to pin message {}: {}", messageId, pinError.getMessage());
      }
      statusService.markDelivered(status.id(), status.version(), status.leaseToken(), messageId);
    } catch (Exception failure) {
      log.error("Failed to dispatch pinned daily status id={}: {}", status.id(), failure.getMessage());
      statusService.retry(status.id(), status.leaseToken());
    }
  }
}
