package io.github.foodjournal.infrastructure.gemini;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.application.MediaProcessingException;
import io.github.foodjournal.config.BotProperties;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class TelegramHttpVoiceMediaClientTest {
  @Test
  void requestsTheExactTelegramFileIdThenDownloadsOnlyTheResolvedFile() {
    RestClient.Builder builder = RestClient.builder().baseUrl("https://api.telegram.org");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://api.telegram.org/bot/token/getFile?file_id=voice-42"))
        .andRespond(withSuccess("{\"ok\":true,\"result\":{\"file_path\":\"voice/file.oga\"}}", MediaType.APPLICATION_JSON));
    server.expect(once(), requestTo("https://api.telegram.org/file/bottoken/voice%2Ffile.oga"))
        .andRespond(withSuccess(new byte[] {1, 2, 3}, MediaType.APPLICATION_OCTET_STREAM));

    TelegramHttpVoiceMediaClient client = new TelegramHttpVoiceMediaClient(builder.build(), properties());
    try (TransientVoicePayload payload = client.download("voice-42")) {
      assertThat(payload.bytes()).containsExactly(1, 2, 3);
    }
    server.verify();
  }

  @Test
  void mapsTelegramHttpFailuresWithoutExposingFileOrToken() {
    RestClient.Builder builder = RestClient.builder().baseUrl("https://api.telegram.org");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://api.telegram.org/bot/token/getFile?file_id=voice-42"))
        .andRespond(org.springframework.test.web.client.response.MockRestResponseCreators.withStatus(HttpStatus.SERVICE_UNAVAILABLE));

    org.assertj.core.api.Assertions.assertThatThrownBy(() -> new TelegramHttpVoiceMediaClient(builder.build(), properties()).download("voice-42"))
        .isInstanceOfSatisfying(MediaProcessingException.class, failure -> {
          assertThat(failure.category()).isEqualTo(MediaProcessingException.Category.TELEGRAM_DOWNLOAD);
          assertThat(failure.getMessage()).doesNotContain("voice-42", "token");
        });
    server.verify();
  }

  private BotProperties properties() {
    return new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "");
  }
}
