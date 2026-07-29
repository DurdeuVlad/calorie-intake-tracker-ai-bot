package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "agent_tool_events", uniqueConstraints = @UniqueConstraint(columnNames = {"agent_run_id", "sequence_number"}))
public class AgentToolEvent {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @ManyToOne(fetch = FetchType.LAZY, optional = false) @JoinColumn(name = "agent_run_id", nullable = false) private AgentRun agentRun;
  @Column(name = "sequence_number", nullable = false) private int sequenceNumber;
  @Column(nullable = false) private String toolName;
  @Column(columnDefinition = "text") private String argumentsSummary;
  @Column(nullable = false) private String resultCode;
  @Column(columnDefinition = "text") private String resultSummary;
  private Long latencyMs;
  private String failureCategory;
  @Column(nullable = false) private Instant createdAt;
  protected AgentToolEvent() {}
  public AgentToolEvent(AgentRun run, int sequence, String toolName, String argumentsSummary, String resultCode, String resultSummary, Long latencyMs, String failureCategory, Instant createdAt) {
    this.agentRun=run; this.sequenceNumber=sequence; this.toolName=toolName; this.argumentsSummary=argumentsSummary; this.resultCode=resultCode; this.resultSummary=resultSummary; this.latencyMs=latencyMs; this.failureCategory=failureCategory; this.createdAt=createdAt;
  }
  public Long getId(){return id;} public AgentRun getAgentRun(){return agentRun;} public int getSequenceNumber(){return sequenceNumber;} public String getToolName(){return toolName;} public String getArgumentsSummary(){return argumentsSummary;} public String getResultCode(){return resultCode;} public String getResultSummary(){return resultSummary;} public Long getLatencyMs(){return latencyMs;} public String getFailureCategory(){return failureCategory;} public Instant getCreatedAt(){return createdAt;}
}
