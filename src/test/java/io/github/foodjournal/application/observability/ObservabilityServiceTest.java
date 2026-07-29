package io.github.foodjournal.application.observability;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ObservabilityServiceTest {
  private final AgentRunRepository runs=mock(AgentRunRepository.class);
  private final AgentToolEventRepository tools=mock(AgentToolEventRepository.class);
  private final IntegrationEventRepository integrations=mock(IntegrationEventRepository.class);
  private final AgentTracePayloadRepository payloads=mock(AgentTracePayloadRepository.class);
  private final AuditEventRepository audits=mock(AuditEventRepository.class);
  private final Clock clock=Clock.fixed(Instant.parse("2026-07-30T10:00:00Z"), ZoneOffset.UTC);

  @Test void storesOnlyCiphertextAndAClassifiedPreviewForPrivatePayload() {
    TracePayloadCipher cipher=new TracePayloadCipher(){public String encrypt(String value){return "encrypted:"+value.length();} public String decrypt(String value){return "meal";}};
    ObservabilityService service=service(cipher); UUID id=UUID.randomUUID(); AgentRun run=AgentRun.started(id, 7L, new FoodUser(1L,"A"),"TEXT","gpt-test",Instant.now(clock));
    when(runs.findById(id)).thenReturn(Optional.of(run));

    service.storePrivatePayload(id, AgentTracePayload.Type.INPUT, "private meal text");

    verify(payloads).save(argThat(payload -> payload.getEncryptedPayload().equals("encrypted:17")
        && payload.getRedactedPreview().equals("[private input, 17 chars]")));
  }

  @Test void doesNotPersistPrivatePayloadWhenNoCipherIsInstalled() {
    ObservabilityService service=service(null);
    service.storePrivatePayload(UUID.randomUUID(), AgentTracePayload.Type.INPUT, "private meal text");
    verifyNoInteractions(runs, payloads);
  }

  @Test void recordsToolOutcomeAndIncrementsTheRunCounter() {
    ObservabilityService service=service(null); UUID id=UUID.randomUUID(); AgentRun run=AgentRun.started(id,null,new FoodUser(1L,"A"),"TEXT",null,Instant.now(clock));
    when(runs.findById(id)).thenReturn(Optional.of(run));
    service.recordTool(id,1,"get_today_summary","no arguments","OK","summary available",12L,null);
    verify(tools).save(argThat(event -> event.getSequenceNumber()==1 && event.getResultCode().equals("OK") && event.getLatencyMs()==12L));
    org.assertj.core.api.Assertions.assertThat(run.getToolCallCount()).isEqualTo(1);
  }

  private ObservabilityService service(TracePayloadCipher cipher) {
    return new ObservabilityService(runs,tools,integrations,payloads,audits,cipher,clock);
  }
}
