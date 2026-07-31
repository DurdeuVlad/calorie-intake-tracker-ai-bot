package io.github.foodjournal.infrastructure.openai;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.foodjournal.application.MediaProcessingException;
import io.github.foodjournal.application.VoiceTranscriptionProvider;
import io.github.foodjournal.config.BotProperties;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

@Component
public class OpenAiVoiceTranscriptionProvider implements VoiceTranscriptionProvider {
  private final RestClient openai;
  private final BotProperties properties;

  @Autowired public OpenAiVoiceTranscriptionProvider(RestClient.Builder builder, BotProperties properties) {
    this(builder.baseUrl("https://api.openai.com/v1").build(), properties);
  }

  OpenAiVoiceTranscriptionProvider(RestClient openai, BotProperties properties) {
    this.openai = openai;
    this.properties = properties;
  }

  @Override public String name() { return "openai"; }

  @Override public String transcribe(byte[] bytes, String mimeType) {
    if (properties.openaiApiKey() == null || properties.openaiApiKey().isBlank()) throw failure(MediaProcessingException.Category.NOT_CONFIGURED, "OpenAI transcription is not configured");
    MultiValueMap<String,Object> form = new LinkedMultiValueMap<>();
    form.add("model", properties.openaiTranscriptionModel());
    HttpHeaders fileHeaders = new HttpHeaders(); fileHeaders.setContentType(mediaType(mimeType));
    form.add("file", new HttpEntity<>(new ByteArrayResource(bytes) { @Override public String getFilename() { return "voice.ogg"; } }, fileHeaders));
    try {
      JsonNode response = openai.post().uri("/audio/transcriptions")
          .header("Authorization", "Bearer " + properties.openaiApiKey())
          .contentType(MediaType.MULTIPART_FORM_DATA).body(form).retrieve().body(JsonNode.class);
      String text = response == null ? null : response.path("text").asText(null);
      if (text == null || text.isBlank()) throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "OpenAI returned no transcript");
      return text.trim();
    } catch (MediaProcessingException expected) {
      throw expected;
    } catch (RestClientResponseException failure) {
      throw providerFailure(failure);
    } catch (ResourceAccessException failure) {
      throw failure(MediaProcessingException.Category.PROVIDER_TEMPORARY, "OpenAI is temporarily unavailable", failure);
    } catch (RuntimeException failure) {
      throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "OpenAI returned an invalid transcription response", failure);
    }
  }

  private MediaType mediaType(String value) { try { return value == null || value.isBlank() ? MediaType.valueOf("audio/ogg") : MediaType.valueOf(value); } catch (IllegalArgumentException ignored) { return MediaType.APPLICATION_OCTET_STREAM; } }
  private MediaProcessingException providerFailure(RestClientResponseException failure) { int status = failure.getStatusCode().value(); if (status == 401 || status == 403) return failure(MediaProcessingException.Category.NOT_CONFIGURED, "OpenAI transcription is not configured", failure); if (status == 404) return failure(MediaProcessingException.Category.MODEL_UNAVAILABLE, "OpenAI transcription model is unavailable", failure); if (status == 429) return failure(MediaProcessingException.Category.RATE_LIMITED, "OpenAI is rate limited", failure); if (status >= 500) return failure(MediaProcessingException.Category.PROVIDER_TEMPORARY, "OpenAI is temporarily unavailable", failure); return failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "OpenAI rejected the transcription request", failure); }
  private MediaProcessingException failure(MediaProcessingException.Category category, String message) { return new MediaProcessingException(category, message); }
  private MediaProcessingException failure(MediaProcessingException.Category category, String message, Throwable cause) { return new MediaProcessingException(category, message, cause); }
}
