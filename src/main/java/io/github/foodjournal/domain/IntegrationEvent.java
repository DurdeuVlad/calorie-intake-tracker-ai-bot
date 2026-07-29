package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity @Table(name = "integration_events")
public class IntegrationEvent {
  public enum Outcome { SUCCEEDED, FAILED }
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "agent_run_id") private AgentRun agentRun;
  @Column(nullable = false) private String provider;
  @Column(nullable = false) private String operation;
  private String modelAlias;
  @Enumerated(EnumType.STRING) @Column(nullable = false) private Outcome outcome;
  private Long latencyMs;
  private String errorCategory;
  @Column(nullable = false) private Instant createdAt;
  protected IntegrationEvent() {}
  public IntegrationEvent(AgentRun run, String provider, String operation, String modelAlias, Outcome outcome, Long latencyMs, String errorCategory, Instant createdAt) {
    this.agentRun=run;this.provider=provider;this.operation=operation;this.modelAlias=modelAlias;this.outcome=outcome;this.latencyMs=latencyMs;this.errorCategory=errorCategory;this.createdAt=createdAt;
  }
  public Long getId(){return id;} public AgentRun getAgentRun(){return agentRun;} public String getProvider(){return provider;} public String getOperation(){return operation;} public String getModelAlias(){return modelAlias;} public Outcome getOutcome(){return outcome;} public Long getLatencyMs(){return latencyMs;} public String getErrorCategory(){return errorCategory;} public Instant getCreatedAt(){return createdAt;}
}
