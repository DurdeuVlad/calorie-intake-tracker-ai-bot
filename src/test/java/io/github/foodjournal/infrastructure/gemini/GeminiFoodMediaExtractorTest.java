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

import io.github.foodjournal.application.FoodMediaType;
import io.github.foodjournal.application.MediaProcessingException;
import io.github.foodjournal.application.TelegramVoiceMediaClient;
import io.github.foodjournal.application.TransientVoicePayload;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class GeminiFoodMediaExtractorTest {
  @Test
  void extractsPhotoEvidenceAndErasesBytes() {
    byte[] downloaded = {1, 2, 3};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/test-gemini:generateContent"))
        .andExpect(header("x-goog-api-key", "key"))
        .andExpect(content().string(org.hamcrest.Matchers.containsString("AQID")))
        .andExpect(jsonPath("$.contents[0].parts[1].inline_data.mime_type").value("image/jpeg"))
        .andExpect(jsonPath("$.contents[0].parts[1].inline_data.data").value("AQID"))
        .andRespond(withSuccess("{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"Oat bar, 180 kcal\"}]}}]}", MediaType.APPLICATION_JSON));

    String extraction = new GeminiFoodMediaExtractor(media(downloaded), builder.build(), "key", "test-gemini").extract("photo", "image/jpeg", FoodMediaType.PHOTO);

    assertThat(extraction).isEqualTo("Oat bar, 180 kcal");
    assertThat(downloaded).containsOnly((byte) 0);
    server.verify();
  }

  @Test
  void rejectsNonPdfDocumentsBeforeDownloadingAnything() {
    TelegramVoiceMediaClient media = org.mockito.Mockito.mock(TelegramVoiceMediaClient.class);

    assertThatThrownBy(() -> new GeminiFoodMediaExtractor(media, RestClient.create(), "key")
        .extract("document", "text/plain", FoodMediaType.DOCUMENT)).isInstanceOfSatisfying(MediaProcessingException.class, failure -> assertThat(failure.category()).isEqualTo(MediaProcessingException.Category.INVALID_MEDIA));

    org.mockito.Mockito.verifyNoInteractions(media);
  }

  @Test
  void extractsPdfLabelEvidenceAndErasesBytes() {
    byte[] downloaded = {4, 5, 6};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/test-gemini:generateContent"))
        .andExpect(header("x-goog-api-key", "key"))
        .andExpect(content().string(org.hamcrest.Matchers.containsString("application/pdf")))
        .andExpect(content().string(org.hamcrest.Matchers.containsString("BAUG")))
        .andRespond(withSuccess("{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"Cereal, 120 kcal per serving\"}]}}]}", MediaType.APPLICATION_JSON));

    String extraction = new GeminiFoodMediaExtractor(media(downloaded), builder.build(), "key", "test-gemini").extract("document", "application/pdf", FoodMediaType.DOCUMENT);

    assertThat(extraction).isEqualTo("Cereal, 120 kcal per serving");
    assertThat(downloaded).containsOnly((byte) 0);
    server.verify();
  }

  @Test
  void mapsUnavailableModelAndErasesPhotoBytes() {
    byte[] downloaded = {1, 2, 3};
    RestClient.Builder builder = RestClient.builder().baseUrl("https://generativelanguage.googleapis.com/v1beta");
    MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    server.expect(once(), requestTo("https://generativelanguage.googleapis.com/v1beta/models/test-gemini:generateContent"))
        .andRespond(withStatus(HttpStatus.NOT_FOUND));

    assertThatThrownBy(() -> new GeminiFoodMediaExtractor(media(downloaded), builder.build(), "key", "test-gemini").extract("photo", "image/jpeg", FoodMediaType.PHOTO))
        .isInstanceOfSatisfying(MediaProcessingException.class, failure -> assertThat(failure.category()).isEqualTo(MediaProcessingException.Category.MODEL_UNAVAILABLE));

    assertThat(downloaded).containsOnly((byte) 0);
    server.verify();
  }

  private TelegramVoiceMediaClient media(byte[] bytes) { return ignored -> new TransientVoicePayload(bytes); }
}
