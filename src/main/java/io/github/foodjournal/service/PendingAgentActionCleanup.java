package io.github.foodjournal.service;

import io.github.foodjournal.repository.PendingAgentActionRepository;
import java.time.Instant;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@ConditionalOnProperty(prefix="food-journal", name="scheduling-enabled", havingValue="true", matchIfMissing=true)
public class PendingAgentActionCleanup {
 private final PendingAgentActionRepository actions;
 public PendingAgentActionCleanup(PendingAgentActionRepository actions){this.actions=actions;}
 @Scheduled(fixedDelayString="${food-journal.pending-agent-action-cleanup-delay-ms:900000}")
 @Transactional public void purge(){actions.deleteByExpiresAtBefore(Instant.now());}
}
