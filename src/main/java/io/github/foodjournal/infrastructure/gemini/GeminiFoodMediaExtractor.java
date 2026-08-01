package io.github.foodjournal.infrastructure.gemini;

import io.github.foodjournal.application.FoodMediaExtractor;
import io.github.foodjournal.application.FoodMediaType;
import io.github.foodjournal.application.MediaProcessingException;
import io.github.foodjournal.application.TelegramVoiceMediaClient;
import io.github.foodjournal.application.TransientVoicePayload;
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
public class GeminiFoodMediaExtractor implements FoodMediaExtractor {
  private final TelegramVoiceMediaClient mediaClient;
  private final RestClient gemini;
  private final String apiKey;
  private final String model;

  @Autowired
  public GeminiFoodMediaExtractor(TelegramVoiceMediaClient mediaClient, RestClient.Builder builder,
      BotProperties properties) {
    this(mediaClient, builder.baseUrl("https://generativelanguage.googleapis.com/v1beta").build(), properties.geminiApiKey(), properties.geminiModel());
  }

  GeminiFoodMediaExtractor(TelegramVoiceMediaClient mediaClient, RestClient gemini, String apiKey) {
    this(mediaClient, gemini, apiKey, "gemini-3.6-flash");
  }

  GeminiFoodMediaExtractor(TelegramVoiceMediaClient mediaClient, RestClient gemini, String apiKey, String model) {
    this.mediaClient = mediaClient;
    this.gemini = gemini;
    this.apiKey = apiKey;
    this.model = model;
  }

  @Override
  public String extract(String telegramFileId, String mimeType, FoodMediaType type) {
    if (apiKey == null || apiKey.isBlank()) throw failure(MediaProcessingException.Category.NOT_CONFIGURED, "Media provider is not configured");
    String safeMimeType = supportedMimeType(mimeType, type);
    try (TransientVoicePayload payload = download(telegramFileId)) {
      return extract(payload.bytes(), mimeType, type);
    } catch (MediaProcessingException expected) {
      throw expected;
    } catch (RuntimeException downloadFailure) {
      throw failure(MediaProcessingException.Category.TELEGRAM_DOWNLOAD, "Telegram media download failed", downloadFailure);
    }
  }

  @Override public String extract(byte[] bytes, String mimeType, FoodMediaType type) {
    if (apiKey == null || apiKey.isBlank()) throw failure(MediaProcessingException.Category.NOT_CONFIGURED, "Media provider is not configured");
    String safeMimeType = supportedMimeType(mimeType, type);
    if (bytes == null || bytes.length == 0 || bytes.length > 20_000_000) throw failure(MediaProcessingException.Category.INVALID_MEDIA, "Media payload is invalid");
    Map<String, Object> body = Map.of("contents", List.of(Map.of("parts", List.of(
          Map.of("text", prompt(type)), Map.of("inline_data", Map.of("mime_type", safeMimeType,
              "data", Base64.getEncoder().encodeToString(bytes)))))));
    try {
      Map<?, ?> response = gemini.post().uri("/models/{model}:generateContent", model)
          .header("x-goog-api-key", apiKey).body(body).retrieve().body(Map.class);
      return extractedText(response);
    } catch (RestClientResponseException responseFailure) {
      throw providerFailure(responseFailure);
    } catch (ResourceAccessException connectionFailure) {
      throw failure(MediaProcessingException.Category.PROVIDER_TEMPORARY, "Media provider is temporarily unavailable", connectionFailure);
    }
  }

  private String supportedMimeType(String mimeType, FoodMediaType type) {
    if (type == FoodMediaType.PHOTO && mimeType != null && mimeType.startsWith("image/")) return mimeType;
    if (type == FoodMediaType.PHOTO && mimeType == null) return "image/jpeg";
    if (type == FoodMediaType.DOCUMENT && "application/pdf".equals(mimeType)) return mimeType;
    throw failure(MediaProcessingException.Category.INVALID_MEDIA, "Unsupported media type");
  }

  private String prompt(FoodMediaType type) {
    return type == FoodMediaType.PHOTO
        ? "Extract only food and nutrition-label evidence visible in this image. State food names, portions, serving sizes, calories and macros only when legible. Do not invent missing values. Return a concise plain-text meal description suitable for a food journal."
        : "Extract only food and nutrition-label evidence visible in this PDF. State food names, portions, serving sizes, calories and macros only when legible. Do not invent missing values. Return a concise plain-text meal description suitable for a food journal.";
  }

  private String extractedText(Map<?, ?> response) {
    Object candidates = response == null ? null : response.get("candidates");
    if (!(candidates instanceof List<?> candidateList) || candidateList.isEmpty() || !(candidateList.getFirst() instanceof Map<?, ?> candidate)) throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "Media provider returned no extraction");
    Object content = candidate.get("content"); Object parts = content instanceof Map<?, ?> map ? map.get("parts") : null;
    if (!(parts instanceof List<?> partList) || partList.isEmpty() || !(partList.getFirst() instanceof Map<?, ?> part) || !(part.get("text") instanceof String text) || text.isBlank()) throw failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "Media provider returned no extraction");
    return text.trim();
  }

  private TransientVoicePayload download(String telegramFileId) { return mediaClient.download(telegramFileId); }

  private MediaProcessingException providerFailure(RestClientResponseException responseFailure) {
    int status = responseFailure.getStatusCode().value();
    if (status == 401 || status == 403) return failure(MediaProcessingException.Category.NOT_CONFIGURED, "Media provider is not configured", responseFailure);
    if (status == 404) return failure(MediaProcessingException.Category.MODEL_UNAVAILABLE, "Media model is unavailable", responseFailure);
    if (status == 429) return failure(MediaProcessingException.Category.RATE_LIMITED, "Media provider is rate limited", responseFailure);
    if (status >= 500) return failure(MediaProcessingException.Category.PROVIDER_TEMPORARY, "Media provider is temporarily unavailable", responseFailure);
    return failure(MediaProcessingException.Category.PROVIDER_RESPONSE, "Media provider rejected the request", responseFailure);
  }

  private MediaProcessingException failure(MediaProcessingException.Category category, String message) { return new MediaProcessingException(category, message); }
  private MediaProcessingException failure(MediaProcessingException.Category category, String message, Throwable cause) { return new MediaProcessingException(category, message, cause); }
}
