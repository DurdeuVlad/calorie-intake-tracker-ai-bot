package io.github.foodjournal.repository;

import io.github.foodjournal.domain.AgentToolEvent;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentToolEventRepository extends JpaRepository<AgentToolEvent, Long> {
  long deleteByCreatedAtBefore(Instant cutoff);
  List<AgentToolEvent> findByAgentRunCorrelationIdOrderBySequenceNumber(UUID correlationId);
}
