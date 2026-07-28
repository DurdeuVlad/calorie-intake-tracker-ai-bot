package io.github.foodjournal.infrastructure.gemini;

import io.github.foodjournal.application.FoodMediaExtractor;
import io.github.foodjournal.application.FoodMediaType;
import io.github.foodjournal.application.TelegramVoiceMediaClient;
import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.config.BotProperties;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class GeminiFoodMediaExtractor implements FoodMediaExtractor {
  private final TelegramVoiceMediaClient mediaClient;
  private final RestClient gemini;
  private final String apiKey;

  @Autowired
  public GeminiFoodMediaExtractor(TelegramVoiceMediaClient mediaClient, RestClient.Builder builder,
      BotProperties properties) {
    this(mediaClient, builder.baseUrl("https://generativelanguage.googleapis.com/v1beta").build(), properties.geminiApiKey());
  }

  GeminiFoodMediaExtractor(TelegramVoiceMediaClient mediaClient, RestClient gemini, String apiKey) {
    this.mediaClient = mediaClient;
    this.gemini = gemini;
    this.apiKey = apiKey;
  }

  @Override
  public String extract(String telegramFileId, String mimeType, FoodMediaType type) {
    if (apiKey == null || apiKey.isBlank()) throw new IllegalStateException("Gemini is not configured");
    String safeMimeType = supportedMimeType(mimeType, type);
    try (TransientVoicePayload payload = mediaClient.download(telegramFileId)) {
      byte[] bytes = payload.bytes();
      if (bytes == null || bytes.length == 0 || bytes.length > 20_000_000) throw new IllegalStateException("Invalid media payload");
      Map<String, Object> body = Map.of("contents", List.of(Map.of("parts", List.of(
          Map.of("text", prompt(type)), Map.of("inline_data", Map.of("mime_type", safeMimeType,
              "data", Base64.getEncoder().encodeToString(bytes)))))));
      Map<?, ?> response = gemini.post().uri("/models/gemini-2.0-flash:generateContent?key={key}", apiKey)
          .body(body).retrieve().body(Map.class);
      return extractedText(response);
    }
  }

  private String supportedMimeType(String mimeType, FoodMediaType type) {
    if (type == FoodMediaType.PHOTO && mimeType != null && mimeType.startsWith("image/")) return mimeType;
    if (type == FoodMediaType.PHOTO && mimeType == null) return "image/jpeg";
    if (type == FoodMediaType.DOCUMENT && "application/pdf".equals(mimeType)) return mimeType;
    throw new IllegalArgumentException("Unsupported media type");
  }

  private String prompt(FoodMediaType type) {
    return type == FoodMediaType.PHOTO
        ? "Extract only food and nutrition-label evidence visible in this image. State food names, portions, serving sizes, calories and macros only when legible. Do not invent missing values. Return a concise plain-text meal description suitable for a food journal."
        : "Extract only food and nutrition-label evidence visible in this PDF. State food names, portions, serving sizes, calories and macros only when legible. Do not invent missing values. Return a concise plain-text meal description suitable for a food journal.";
  }

  private String extractedText(Map<?, ?> response) {
    Object candidates = response == null ? null : response.get("candidates");
    if (!(candidates instanceof List<?> candidateList) || candidateList.isEmpty() || !(candidateList.getFirst() instanceof Map<?, ?> candidate)) throw new IllegalStateException("Gemini extraction unavailable");
    Object content = candidate.get("content"); Object parts = content instanceof Map<?, ?> map ? map.get("parts") : null;
    if (!(parts instanceof List<?> partList) || partList.isEmpty() || !(partList.getFirst() instanceof Map<?, ?> part) || !(part.get("text") instanceof String text) || text.isBlank()) throw new IllegalStateException("Gemini extraction unavailable");
    return text.trim();
  }
}
