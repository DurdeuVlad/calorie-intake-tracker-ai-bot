package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.Instant;

/** Encrypted user-facing input/reply evidence. Never use this for prompts, reasoning, media or provider payloads. */
@Entity @Table(name = "agent_trace_payloads", uniqueConstraints = @UniqueConstraint(columnNames = {"agent_run_id", "payload_type"}))
public class AgentTracePayload {
  public enum Type { INPUT, FINAL_REPLY }
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
  @ManyToOne(fetch = FetchType.LAZY, optional = false) @JoinColumn(name = "agent_run_id", nullable = false) private AgentRun agentRun;
  @Enumerated(EnumType.STRING) @Column(name = "payload_type", nullable = false) private Type type;
  @Column(nullable = false, columnDefinition = "text") private String encryptedPayload;
  @Column(nullable = false, length = 512) private String redactedPreview;
  @Column(nullable = false) private Instant createdAt;
  protected AgentTracePayload() {}
  public AgentTracePayload(AgentRun run, Type type, String encryptedPayload, String redactedPreview, Instant createdAt) { this.agentRun=run;this.type=type;this.encryptedPayload=encryptedPayload;this.redactedPreview=redactedPreview;this.createdAt=createdAt; }
  public Long getId(){return id;} public AgentRun getAgentRun(){return agentRun;} public Type getType(){return type;} public String getEncryptedPayload(){return encryptedPayload;} public String getRedactedPreview(){return redactedPreview;} public Instant getCreatedAt(){return createdAt;}
}
