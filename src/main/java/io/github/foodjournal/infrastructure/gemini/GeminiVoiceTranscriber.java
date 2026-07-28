package io.github.foodjournal.infrastructure.gemini;

import io.github.foodjournal.application.TelegramVoiceMediaClient;
import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.application.VoiceTranscriber;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class GeminiVoiceTranscriber implements VoiceTranscriber {
  private static final int MAX_VOICE_BYTES = 20_000_000;
  private final TelegramVoiceMediaClient mediaClient;
  private final RestClient gemini;
  private final String apiKey;

  @Autowired
  public GeminiVoiceTranscriber(TelegramVoiceMediaClient mediaClient, RestClient.Builder builder,
      @Value("${GEMINI_API_KEY:}") String apiKey) {
    this(mediaClient, builder.baseUrl("https://generativelanguage.googleapis.com/v1beta").build(), apiKey);
  }

  GeminiVoiceTranscriber(TelegramVoiceMediaClient mediaClient, RestClient gemini, String apiKey) {
    this.mediaClient = mediaClient;
    this.gemini = gemini;
    this.apiKey = apiKey;
  }

  @Override
  public String transcribe(String telegramFileId, String mimeType) {
    if (apiKey == null || apiKey.isBlank()) throw new IllegalStateException("Gemini is not configured");
    try (TransientVoicePayload payload = mediaClient.download(telegramFileId)) {
      byte[] bytes = payload.bytes();
      if (bytes == null || bytes.length == 0 || bytes.length > MAX_VOICE_BYTES) {
        throw new IllegalStateException("Invalid voice payload");
      }
      Map<String, Object> body = Map.of("contents", List.of(Map.of("parts", List.of(
          Map.of("text", "Transcribe this voice note exactly. Return only the transcript."),
          Map.of("inline_data", Map.of("mime_type", mimeType == null ? "audio/ogg" : mimeType,
              "data", Base64.getEncoder().encodeToString(bytes)))))));
      Map<?, ?> response = gemini.post().uri("/models/gemini-2.0-flash:generateContent?key={key}", apiKey)
          .body(body).retrieve().body(Map.class);
      return transcript(response);
    }
  }

  private String transcript(Map<?, ?> response) {
    Object candidates = response == null ? null : response.get("candidates");
    if (!(candidates instanceof List<?> candidatesList) || candidatesList.isEmpty() || !(candidatesList.getFirst() instanceof Map<?, ?> candidate)) {
      throw new IllegalStateException("Gemini transcript unavailable");
    }
    Object content = candidate.get("content");
    Object parts = content instanceof Map<?, ?> map ? map.get("parts") : null;
    if (!(parts instanceof List<?> partsList) || partsList.isEmpty() || !(partsList.getFirst() instanceof Map<?, ?> part)
        || !(part.get("text") instanceof String text)) {
      throw new IllegalStateException("Gemini transcript unavailable");
    }
    return text.trim();
  }
}
