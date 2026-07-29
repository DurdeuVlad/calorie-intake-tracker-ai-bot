package io.github.foodjournal.service;

import io.github.foodjournal.application.observability.ObservabilityService;
import io.github.foodjournal.config.AdminProperties;
import java.time.Instant;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class ObservabilityRetentionCleanup {
  private final ObservabilityService traces; private final AdminProperties properties;
  public ObservabilityRetentionCleanup(ObservabilityService traces, AdminProperties properties){this.traces=traces;this.properties=properties;}
  @Scheduled(cron="${food-journal.admin.trace-cleanup-cron:0 17 3 * * *}") public void purge(){traces.purgeDetailedTracesBefore(Instant.now().minus(java.time.Duration.ofDays(properties.traceRetentionDays())));}
}
