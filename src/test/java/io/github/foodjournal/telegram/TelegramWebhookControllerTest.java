package io.github.foodjournal.telegram;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.messaging.InboundMessage;
import io.github.foodjournal.messaging.MessagingIngressService;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class TelegramWebhookControllerTest {
  @Test void rejectsIncorrectWebhookSecretWithoutHandlingUpdate() {
    MessagingIngressService ingress = mock(MessagingIngressService.class);
    TelegramWebhookController controller = new TelegramWebhookController(new BotProperties("token", "expected", Set.of(1L), "Europe/Bucharest", "", "test"), ingress);

    var result = controller.webhook("wrong", new TelegramUpdate(1L, null, null));

    org.assertj.core.api.Assertions.assertThat(result.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    verifyNoInteractions(ingress);
  }

  @Test void acceptsCorrectWebhookSecret() {
    MessagingIngressService ingress = mock(MessagingIngressService.class);
    TelegramWebhookController controller = new TelegramWebhookController(new BotProperties("token", "expected", Set.of(1L), "Europe/Bucharest", "", "test"), ingress);
    TelegramUpdate update = new TelegramUpdate(1L, new TelegramMessage(1L, new TelegramChat(1L), new TelegramUser(1L, "A"), "/help", null, null, null), null);

    var result = controller.webhook("expected", update);

    org.assertj.core.api.Assertions.assertThat(result.getStatusCode()).isEqualTo(HttpStatus.OK);
    verify(ingress).accept(any(InboundMessage.class));
  }
}
