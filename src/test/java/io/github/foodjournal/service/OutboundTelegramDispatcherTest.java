package io.github.foodjournal.service;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.OutboundTelegramMessage;
import io.github.foodjournal.repository.OutboundTelegramMessageRepository;
import io.github.foodjournal.telegram.TelegramGateway;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Pageable;

class OutboundTelegramDispatcherTest {
  @Test void sendsPendingMessagesOutsideTheWebhookTransaction() {
    OutboundTelegramMessageRepository repository = mock(OutboundTelegramMessageRepository.class);
    TelegramGateway telegram = mock(TelegramGateway.class);
    OutboundTelegramMessage message = new OutboundTelegramMessage(1L, "Logged");
    when(repository.findByStatusAndNextAttemptAtLessThanEqualOrderById(eq(OutboundTelegramMessage.Status.PENDING), any(), any(Pageable.class))).thenReturn(List.of(message));

    new OutboundTelegramDispatcher(repository, telegram).dispatch();

    verify(telegram).sendMessage(1L, "Logged");
    org.assertj.core.api.Assertions.assertThat(message.getStatus()).isEqualTo(OutboundTelegramMessage.Status.SENT);
  }
}
