package io.github.foodjournal.application.observability;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.Clock;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Safe persistence boundary for operational traces. Callers must provide summaries, never raw
 * prompts, tool JSON, media bytes, credentials, or provider payloads.
 */
@Service
public class ObservabilityService {
  private final AgentRunRepository runs;
  private final AgentToolEventRepository tools;
  private final IntegrationEventRepository integrations;
  private final AgentTracePayloadRepository payloads;
  private final AuditEventRepository audits;
  private final Optional<TracePayloadCipher> cipher;
  private final Clock clock;

  @Autowired public ObservabilityService(AgentRunRepository runs, AgentToolEventRepository tools, IntegrationEventRepository integrations,
      AgentTracePayloadRepository payloads, AuditEventRepository audits, ObjectProvider<TracePayloadCipher> cipher) {
    this(runs, tools, integrations, payloads, audits, cipher.getIfAvailable(), Clock.systemUTC());
  }
  ObservabilityService(AgentRunRepository runs, AgentToolEventRepository tools, IntegrationEventRepository integrations,
      AgentTracePayloadRepository payloads, AuditEventRepository audits, TracePayloadCipher cipher, Clock clock) {
    this.runs=runs; this.tools=tools; this.integrations=integrations; this.payloads=payloads; this.audits=audits;
    this.cipher=Optional.ofNullable(cipher); this.clock=clock;
  }

  @Transactional
  public AgentRun startRun(UUID correlationId, Long telegramUpdateId, FoodUser actor, String inputType, String modelAlias) {
    return runs.save(AgentRun.started(correlationId, telegramUpdateId, actor, required(inputType, "input type"), clean(modelAlias, 128), Instant.now(clock)));
  }

  @Transactional
  public void recordTool(UUID runId, int sequence, String toolName, String safeArgumentsSummary, String resultCode,
      String safeResultSummary, Long latencyMs, String failureCategory) {
    AgentRun run=run(runId); run.incrementToolCalls();
    tools.save(new AgentToolEvent(run, sequence, required(toolName, "tool name"), clean(safeArgumentsSummary, 2000), required(resultCode, "result code"), clean(safeResultSummary, 2000), nonNegative(latencyMs), clean(failureCategory, 64), Instant.now(clock)));
  }

  @Transactional
  public void recordIntegration(UUID runId, String provider, String operation, String modelAlias,
      IntegrationEvent.Outcome outcome, Long latencyMs, String errorCategory) {
    integrations.save(new IntegrationEvent(run(runId), required(provider, "provider"), required(operation, "operation"), clean(modelAlias, 128), outcome, nonNegative(latencyMs), clean(errorCategory, 64), Instant.now(clock)));
  }

  @Transactional
  public void finishRun(UUID runId, AgentRun.Outcome outcome, String safeReplySummary, String errorCategory) {
    run(runId).finish(outcome, clean(safeReplySummary, 2000), clean(errorCategory, 64), Instant.now(clock));
  }

  /** Stores ciphertext only. Without a cipher this is a safe no-op, allowing observability metadata to remain available. */
  @Transactional
  public void storePrivatePayload(UUID runId, AgentTracePayload.Type type, String plaintext) {
    if (plaintext==null || plaintext.isBlank() || cipher.isEmpty()) return;
    AgentRun run=run(runId);
    String encrypted=cipher.get().encrypt(plaintext);
    if (encrypted==null || encrypted.isBlank()) throw new IllegalStateException("Trace cipher returned no ciphertext");
    payloads.save(new AgentTracePayload(run, type, encrypted, "[private " + type.name().toLowerCase() + ", " + plaintext.length() + " chars]", Instant.now(clock)));
  }

  @Transactional(readOnly = true)
  public Optional<String> revealPrivatePayload(UUID runId, AgentTracePayload.Type type) {
    if (cipher.isEmpty()) return Optional.empty();
    return payloads.findByAgentRunCorrelationIdAndType(runId, type).map(payload -> cipher.get().decrypt(payload.getEncryptedPayload()));
  }

  @Transactional
  public void audit(String actorType, String actorIdentifier, String action, String targetType, String targetIdentifier, String reason, String safeMetadataSummary) {
    audits.save(new AuditEvent(required(actorType, "actor type"), required(actorIdentifier, "actor identifier"), required(action, "action"), clean(targetType, 64), clean(targetIdentifier, 255), clean(reason, 512), clean(safeMetadataSummary, 2000), Instant.now(clock)));
  }

  @Transactional
  public void purgeDetailedTracesBefore(Instant cutoff) {
    payloads.deleteByCreatedAtBefore(cutoff); integrations.deleteByCreatedAtBefore(cutoff); tools.deleteByCreatedAtBefore(cutoff); runs.deleteAll(runs.findByStartedAtBefore(cutoff));
  }

  private AgentRun run(UUID id) { return runs.findById(id).orElseThrow(() -> new IllegalArgumentException("Unknown agent run")); }
  private static String required(String value, String label) { if(value==null||value.isBlank())throw new IllegalArgumentException("Missing " + label); return value.trim(); }
  private static Long nonNegative(Long value) { if(value!=null&&value<0)throw new IllegalArgumentException("Latency must not be negative"); return value; }
  private static String clean(String value, int max) { if(value==null)return null; String compact=value.trim(); return compact.length()<=max?compact:compact.substring(0,max); }
}
