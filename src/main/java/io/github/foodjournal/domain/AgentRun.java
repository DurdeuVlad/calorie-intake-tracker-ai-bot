package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

/** Persisted execution metadata only; prompts, reasoning and provider payloads are deliberately excluded. */
@Entity
@Table(name = "agent_runs")
public class AgentRun {
  public enum Outcome { RUNNING, SUCCEEDED, FAILED, LOOP_LIMIT }

  @Id @Column(name = "correlation_id", nullable = false, updatable = false) private UUID correlationId;
  private Long telegramUpdateId;
  @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "actor_user_id") private FoodUser actor;
  @Column(nullable = false) private String inputType;
  private String modelAlias;
  @Enumerated(EnumType.STRING) @Column(nullable = false) private Outcome outcome = Outcome.RUNNING;
  @Column(nullable = false) private Instant startedAt;
  private Instant finishedAt;
  @Column(nullable = false) private int toolCallCount;
  @Column(columnDefinition = "text") private String finalReplySummary;
  private String errorCategory;

  protected AgentRun() {}
  private AgentRun(UUID correlationId, Long telegramUpdateId, FoodUser actor, String inputType, String modelAlias, Instant startedAt) {
    this.correlationId = correlationId; this.telegramUpdateId = telegramUpdateId; this.actor = actor;
    this.inputType = inputType; this.modelAlias = modelAlias; this.startedAt = startedAt;
  }
  public static AgentRun started(UUID correlationId, Long telegramUpdateId, FoodUser actor, String inputType, String modelAlias, Instant startedAt) {
    return new AgentRun(correlationId, telegramUpdateId, actor, inputType, modelAlias, startedAt);
  }
  public void incrementToolCalls() { toolCallCount++; }
  public void finish(Outcome outcome, String replySummary, String errorCategory, Instant finishedAt) {
    if (this.outcome != Outcome.RUNNING) throw new IllegalStateException("Agent run is already finished");
    this.outcome = outcome; this.finalReplySummary = replySummary; this.errorCategory = errorCategory; this.finishedAt = finishedAt;
  }
  public UUID getCorrelationId() { return correlationId; } public Long getTelegramUpdateId() { return telegramUpdateId; }
  public FoodUser getActor() { return actor; } public String getInputType() { return inputType; }
  public String getModelAlias() { return modelAlias; } public Outcome getOutcome() { return outcome; }
  public Instant getStartedAt() { return startedAt; } public Instant getFinishedAt() { return finishedAt; }
  public int getToolCallCount() { return toolCallCount; } public String getFinalReplySummary() { return finalReplySummary; }
  public String getErrorCategory() { return errorCategory; }
}
