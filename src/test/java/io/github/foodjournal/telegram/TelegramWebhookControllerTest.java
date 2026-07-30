package io.github.foodjournal.telegram;

import static org.mockito.Mockito.*;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.service.UpdateService;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class TelegramWebhookControllerTest {
  @Test void rejectsIncorrectWebhookSecretWithoutHandlingUpdate() {
    UpdateService service = mock(UpdateService.class);
    TelegramWebhookController controller = new TelegramWebhookController(new BotProperties("token", "expected", Set.of(1L), "Europe/Bucharest", "", "test"), service);

    var result = controller.webhook("wrong", new TelegramUpdate(1L, null, null));

    org.assertj.core.api.Assertions.assertThat(result.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    verifyNoInteractions(service);
  }

  @Test void acceptsCorrectWebhookSecret() {
    UpdateService service = mock(UpdateService.class);
    TelegramWebhookController controller = new TelegramWebhookController(new BotProperties("token", "expected", Set.of(1L), "Europe/Bucharest", "", "test"), service);
    TelegramUpdate update = new TelegramUpdate(1L, new TelegramMessage(1L, new TelegramChat(1L), new TelegramUser(1L, "A"), "/help", null, null, null), null);

    var result = controller.webhook("expected", update);

    org.assertj.core.api.Assertions.assertThat(result.getStatusCode()).isEqualTo(HttpStatus.OK);
    verify(service).enqueue(update);
  }
}
