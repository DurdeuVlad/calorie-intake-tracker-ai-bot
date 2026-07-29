package io.github.foodjournal.service;

import static org.mockito.Mockito.*;

import io.github.foodjournal.application.JournalApplicationService;
import org.junit.jupiter.api.Test;

class PendingFoodDraftCleanupTest {
  @Test void scheduledCleanupDelegatesToTransactionalDraftPurge() {
    JournalApplicationService journal = mock(JournalApplicationService.class);
    new PendingFoodDraftCleanup(journal).removeExpiredDrafts();
    verify(journal).purgeExpiredDrafts();
  }
}
