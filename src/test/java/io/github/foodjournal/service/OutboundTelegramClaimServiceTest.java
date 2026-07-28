package io.github.foodjournal.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.OutboundTelegramMessage;
import io.github.foodjournal.repository.OutboundTelegramMessageRepository;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class OutboundTelegramClaimServiceTest {
  @Test void staleWorkerCannotCompleteANewerLease() {
    OutboundTelegramMessageRepository messages = mock(OutboundTelegramMessageRepository.class);
    OutboundTelegramMessage message = new OutboundTelegramMessage(1L, "reply");
    message.claim(); UUID stale = message.getLeaseToken();
    message.claim(); UUID current = message.getLeaseToken();
    when(messages.findById(7L)).thenReturn(Optional.of(message));
    OutboundTelegramClaimService service = new OutboundTelegramClaimService(messages);

    service.markSent(7L, stale);
    assertThat(message.getStatus()).isEqualTo(OutboundTelegramMessage.Status.IN_PROGRESS);
    service.markSent(7L, current);
    assertThat(message.getStatus()).isEqualTo(OutboundTelegramMessage.Status.SENT);
  }
}
