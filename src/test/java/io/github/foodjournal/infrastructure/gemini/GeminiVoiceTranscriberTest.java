package io.github.foodjournal.infrastructure.gemini;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.application.TelegramVoiceMediaClient;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class GeminiVoiceTranscriberTest {
  @Test
  void erasesDownloadedBytesAfterSuccessfulTranscription() {
    byte[] downloaded = {7, 8, 9};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=key"))
        .andExpect(content().string(org.hamcrest.Matchers.containsString("BwgJ")))
        .andRespond(withSuccess("{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"two eggs\"}]}}]}", MediaType.APPLICATION_JSON));

    String transcript = new GeminiVoiceTranscriber(media(downloaded), builder.build(), "key").transcribe("voice", "audio/ogg");

    assertThat(transcript).isEqualTo("two eggs");
    assertThat(downloaded).containsOnly((byte) 0);
    server.verify();
  }

  @Test
  void erasesRejectedOversizeBytesWithoutCallingGemini() {
    byte[] downloaded = new byte[20_000_001];

    assertThatThrownBy(() -> new GeminiVoiceTranscriber(media(downloaded), RestClient.create(), "key")
        .transcribe("voice", "audio/ogg"))
        .isInstanceOf(IllegalStateException.class).hasMessage("Invalid voice payload");

    assertThat(downloaded).containsOnly((byte) 0);
  }

  private TelegramVoiceMediaClient media(byte[] bytes) {
    return ignored -> new TransientVoicePayload(bytes);
  }
}
