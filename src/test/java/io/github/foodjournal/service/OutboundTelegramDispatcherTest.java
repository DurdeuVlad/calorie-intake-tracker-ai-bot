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
    java.util.UUID token = java.util.UUID.randomUUID();
    OutboundTelegramClaimService.Delivery message = new OutboundTelegramClaimService.Delivery(7L, 1L, "Logged", 99L, token);
    when(claims.claimBatch()).thenReturn(List.of(message));

    new OutboundTelegramDispatcher(claims, telegram).dispatch();

    verify(telegram).sendMessage(1L, "Logged");
    verify(claims).markSent(7L, token);
  }
  @Test void sendsAnOversizedMessageOnceAtTelegramLimit() {
    OutboundTelegramClaimService claims=mock(OutboundTelegramClaimService.class);TelegramGateway telegram=mock(TelegramGateway.class);java.util.UUID token=java.util.UUID.randomUUID();when(claims.claimBatch()).thenReturn(List.of(new OutboundTelegramClaimService.Delivery(8L,1L,"a".repeat(5000),99L,token)));
    new OutboundTelegramDispatcher(claims,telegram).dispatch();
    verify(telegram).sendMessage(eq(1L),argThat(text->text.length()==4096&&text.endsWith("[Message truncated]")));verify(claims).markSent(8L,token);
  }
}
