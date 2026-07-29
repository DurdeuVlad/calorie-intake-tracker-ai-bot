package io.github.foodjournal.repository;

import io.github.foodjournal.domain.AgentTracePayload;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentTracePayloadRepository extends JpaRepository<AgentTracePayload, Long> {
  Optional<AgentTracePayload> findByAgentRunCorrelationIdAndType(UUID correlationId, AgentTracePayload.Type type);
  long deleteByCreatedAtBefore(Instant cutoff);
}
