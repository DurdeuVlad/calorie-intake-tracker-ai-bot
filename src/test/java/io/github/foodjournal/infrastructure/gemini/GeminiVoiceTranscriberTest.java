package io.github.foodjournal.infrastructure.gemini;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import io.github.foodjournal.application.MediaProcessingException;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class GeminiVoiceTranscriberTest {
  @Test
  void transcribesProvidedTransientBytes() {
    byte[] downloaded = {7, 8, 9};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/test-gemini:generateContent"))
        .andExpect(header("x-goog-api-key", "key"))
        .andExpect(content().string(org.hamcrest.Matchers.containsString("BwgJ")))
        .andExpect(jsonPath("$.contents[0].parts[1].inline_data.mime_type").value("audio/ogg"))
        .andExpect(jsonPath("$.contents[0].parts[1].inline_data.data").value("BwgJ"))
        .andRespond(withSuccess("{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"two eggs\"}]}}]}", MediaType.APPLICATION_JSON));

    String transcript = new GeminiVoiceTranscriber(builder.build(), "key", "test-gemini").transcribe(downloaded, "audio/ogg");

    assertThat(transcript).isEqualTo("two eggs");
    server.verify();
  }

  @Test
  void mapsGeminiHttpFailuresToSafeTypedCategoriesAndErasesBytes() {
    assertProviderFailure(HttpStatus.UNAUTHORIZED, MediaProcessingException.Category.NOT_CONFIGURED);
    assertProviderFailure(HttpStatus.NOT_FOUND, MediaProcessingException.Category.MODEL_UNAVAILABLE);
    assertProviderFailure(HttpStatus.TOO_MANY_REQUESTS, MediaProcessingException.Category.RATE_LIMITED);
    assertProviderFailure(HttpStatus.SERVICE_UNAVAILABLE, MediaProcessingException.Category.PROVIDER_TEMPORARY);
  }

  @Test
  void rejectsMalformedGeminiResponsesAsProviderResponseFailuresAndErasesBytes() {
    byte[] downloaded = {7, 8, 9};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/test-gemini:generateContent"))
        .andRespond(withSuccess("{\"candidates\":[]}", MediaType.APPLICATION_JSON));

    assertThatThrownBy(() -> new GeminiVoiceTranscriber(builder.build(), "key", "test-gemini").transcribe(downloaded, "audio/ogg"))
        .isInstanceOfSatisfying(MediaProcessingException.class, failure -> assertThat(failure.category()).isEqualTo(MediaProcessingException.Category.PROVIDER_RESPONSE));

    server.verify();
  }

  private void assertProviderFailure(HttpStatus status, MediaProcessingException.Category expectedCategory) {
    byte[] downloaded = {7, 8, 9};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/test-gemini:generateContent"))
        .andExpect(header("x-goog-api-key", "key")).andRespond(withStatus(status));

    assertThatThrownBy(() -> new GeminiVoiceTranscriber(builder.build(), "key", "test-gemini").transcribe(downloaded, "audio/ogg"))
        .isInstanceOfSatisfying(MediaProcessingException.class, failure -> assertThat(failure.category()).isEqualTo(expectedCategory));

    server.verify();
  }

}
