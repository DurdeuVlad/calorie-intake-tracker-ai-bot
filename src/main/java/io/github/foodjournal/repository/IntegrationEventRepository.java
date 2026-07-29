package io.github.foodjournal.repository;

import io.github.foodjournal.domain.IntegrationEvent;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface IntegrationEventRepository extends JpaRepository<IntegrationEvent, Long> {
  long deleteByCreatedAtBefore(Instant cutoff);
  List<IntegrationEvent> findByAgentRunCorrelationIdOrderByCreatedAt(UUID correlationId);
}
