package io.github.foodjournal.service;

import io.github.foodjournal.application.JournalApplicationService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Removes expired raw-message drafts even when a user does not send another update. */
@Service
@ConditionalOnProperty(prefix = "food-journal", name = "scheduling-enabled", havingValue = "true", matchIfMissing = true)
public class PendingFoodDraftCleanup {
  private final JournalApplicationService journal;

  public PendingFoodDraftCleanup(JournalApplicationService journal) {
    this.journal = journal;
  }

  @Scheduled(fixedDelayString = "${food-journal.pending-draft-cleanup-delay-ms:900000}")
  public void removeExpiredDrafts() {
    journal.purgeExpiredDrafts();
  }
}
