package io.github.foodjournal.infrastructure.gemini;

import io.github.foodjournal.application.TelegramVoiceMediaClient;
import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.application.VoiceTranscriber;
import io.github.foodjournal.application.MediaProcessingException;
import io.github.foodjournal.config.BotProperties;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.ResourceAccessException;

@Component
public class GeminiVoiceTranscriber implements VoiceTranscriber {
  private static final int MAX_VOICE_BYTES = 20_000_000;
  private final TelegramVoiceMediaClient mediaClient;
  private final RestClient gemini;
  private final String apiKey;
  private final String model;

  @Autowired
  public GeminiVoiceTranscriber(TelegramVoiceMediaClient mediaClient, RestClient.Builder builder,
      BotProperties properties) {
    this(mediaClient, builder.baseUrl("https://generativelanguage.googleapis.com/v1beta").build(), properties.geminiApiKey(), properties.geminiModel());
  }

  GeminiVoiceTranscriber(TelegramVoiceMediaClient mediaClient, RestClient gemini, String apiKey) {
    this(mediaClient, gemini, apiKey, "gemini-3.6-flash");
  }

  GeminiVoiceTranscriber(TelegramVoiceMediaClient mediaClient, RestClient gemini, String apiKey, String model) {
    this.mediaClient = mediaClient;
    this.gemini = gemini;
    this.apiKey = apiKey;
    this.model = model;
  }

  @Override
  public String transcribe(String telegramFileId, String mimeType) {
    if (apiKey == null || apiKey.isBlank()) throw failure(MediaProcessingException.Category.NOT_CONFIGURED, "Media provider is not configured");
    try (TransientVoicePayload payload = download(telegramFileId)) {
      byte[] bytes = payload.bytes();
      if (bytes == null || bytes.length == 0 || bytes.length > MAX_VOICE_BYTES) {
        throw failure(MediaProcessingException.Category.INVALID_MEDIA, "Voice note is invalid");
      }
      Map<String, Object> body = Map.of("contents", List.of(Map.of("parts", List.of(
          Map.of("text", "Transcribe this voice note exactly. Return only the transcript."),
          Map.of("inline_data", Map.of("mime_type", mimeType == null ? "audio/ogg" : mimeType,
              "data", Base64.getEncoder().encodeToString(bytes)))))));
      try {
        Map<?, ?> response = gemini.post().uri("/models/{model}:generateContent", model)
            .header("x-goog-api-key", apiKey).body(body).retrieve().body(Map.class);
        return transcript(response);
      } catch (RestClientResponseException responseFailure) {
        throw providerFailure(responseFailure);
      } catch (ResourceAccessException connectionFailure) {
        throw failure(MediaProcessingException.Category.PROVIDER_TEMPORARY, "Media provider is temporarily unavailable", connectionFailure);
      }
    } catch (MediaProcessingException expected) {
      throw expected;
    } catch (RuntimeException downloadFailure) {
      throw failure(MediaProcessingException.Category.TELEGRAM_DOWNLOAD, "Telegram media download failed", downloadFailure);
    }
  }

  private String transcript(Map<?, ?> response) {
    Object candidates = response == null ? null : response.get("candidates");
    if (!(candidates instanceof List<?> candidatesList) || candidatesList.isEmpty() || !(candidatesList.getFirst() instanceof Map<?, ?> candidate)) {
      throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "Media provider returned no transcript");
    }
    Object content = candidate.get("content");
    Object parts = content instanceof Map<?, ?> map ? map.get("parts") : null;
    if (!(parts instanceof List<?> partsList) || partsList.isEmpty() || !(partsList.getFirst() instanceof Map<?, ?> part)
        || !(part.get("text") instanceof String text)) {
      throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "Media provider returned no transcript");
    }
    return text.trim();
  }

  private TransientVoicePayload download(String telegramFileId) {
    return mediaClient.download(telegramFileId);
  }

  private MediaProcessingException providerFailure(RestClientResponseException responseFailure) {
    int status = responseFailure.getStatusCode().value();
    if (status == 401 || status == 403) return failure(MediaProcessingException.Category.NOT_CONFIGURED, "Media provider is not configured", responseFailure);
    if (status == 404) return failure(MediaProcessingException.Category.MODEL_UNAVAILABLE, "Media model is unavailable", responseFailure);
    if (status == 429) return failure(MediaProcessingException.Category.RATE_LIMITED, "Media provider is rate limited", responseFailure);
    if (status >= 500) return failure(MediaProcessingException.Category.PROVIDER_TEMPORARY, "Media provider is temporarily unavailable", responseFailure);
    return failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "Media provider rejected the request", responseFailure);
  }

  private MediaProcessingException failure(MediaProcessingException.Category category, String message) {
    return new MediaProcessingException(category, message);
  }

  private MediaProcessingException failure(MediaProcessingException.Category category, String message, Throwable cause) {
    return new MediaProcessingException(category, message, cause);
  }
}
