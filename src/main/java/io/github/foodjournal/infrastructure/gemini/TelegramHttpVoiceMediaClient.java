package io.github.foodjournal.infrastructure.gemini;

import io.github.foodjournal.application.TelegramVoiceMediaClient;
import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.config.BotProperties;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class TelegramHttpVoiceMediaClient implements TelegramVoiceMediaClient {
  private final RestClient telegram;
  private final BotProperties properties;

  @Autowired
  public TelegramHttpVoiceMediaClient(RestClient.Builder builder, BotProperties properties) {
    this(builder.baseUrl("https://api.telegram.org").build(), properties);
  }

  TelegramHttpVoiceMediaClient(RestClient telegram, BotProperties properties) {
    this.telegram = telegram;
    this.properties = properties;
  }

  @Override
  public TransientVoicePayload download(String telegramFileId) {
    if (telegramFileId == null || telegramFileId.isBlank()) {
      throw new IllegalArgumentException("Missing Telegram voice file ID");
    }
    Map<?, ?> response = telegram.get().uri(uri -> uri.path("/bot/{token}/getFile")
        .queryParam("file_id", telegramFileId).build(properties.telegramToken()))
        .retrieve().body(Map.class);
    Object result = response == null ? null : response.get("result");
    if (!(result instanceof Map<?, ?> file) || !(file.get("file_path") instanceof String path)) {
      throw new IllegalStateException("Telegram file unavailable");
    }
    return new TransientVoicePayload(telegram.get()
        .uri("/file/bot{token}/{path}", properties.telegramToken(), path)
        .retrieve().body(byte[].class));
  }
}
