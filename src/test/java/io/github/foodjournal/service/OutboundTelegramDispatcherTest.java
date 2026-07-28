package io.github.foodjournal.service;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.telegram.TelegramGateway;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Pageable;

class OutboundTelegramDispatcherTest {
  @Test void sendsPendingMessagesOutsideTheWebhookTransaction() {
    OutboundTelegramClaimService claims = mock(OutboundTelegramClaimService.class);
    TelegramGateway telegram = mock(TelegramGateway.class);
    OutboundTelegramClaimService.Delivery message = new OutboundTelegramClaimService.Delivery(7L, 1L, "Logged");
    when(claims.claimBatch()).thenReturn(List.of(message));

    new OutboundTelegramDispatcher(claims, telegram).dispatch();

    verify(telegram).sendMessage(1L, "Logged");
    verify(claims).markSent(7L);
  }
}
