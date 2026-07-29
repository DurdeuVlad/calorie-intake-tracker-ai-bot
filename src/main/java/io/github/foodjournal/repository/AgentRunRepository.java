package io.github.foodjournal.repository;

import io.github.foodjournal.domain.AgentRun;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentRunRepository extends JpaRepository<AgentRun, UUID> {
  List<AgentRun> findByStartedAtBefore(Instant cutoff);
}
