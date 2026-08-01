package io.github.foodjournal.config;

import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.ConstructorBinding;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("food-journal")
public record BotProperties(
    String telegramToken,
    String webhookSecret,
    Set<Long> allowedTelegramUserIds,
    String defaultTimezone,
    String openaiApiKey,
    String openaiModel,
    int agentMaxToolCalls,
    String geminiApiKey,
    String geminiModel,
    String openaiTranscriptionModel,
    String openFoodFactsBaseUrl) {
  @ConstructorBinding public BotProperties {
    telegramToken = telegramToken == null ? "" : telegramToken;
    webhookSecret = webhookSecret == null ? "" : webhookSecret;
    allowedTelegramUserIds = allowedTelegramUserIds == null ? Set.of() : Set.copyOf(allowedTelegramUserIds);
    defaultTimezone = defaultTimezone == null ? "Europe/Bucharest" : defaultTimezone;
    openaiModel = openaiModel == null ? "gpt-5.4-mini" : openaiModel;
    agentMaxToolCalls = agentMaxToolCalls <= 0 ? 10 : Math.min(agentMaxToolCalls, 10);
    geminiApiKey = geminiApiKey == null ? "" : geminiApiKey;
    geminiModel = geminiModel == null || geminiModel.isBlank() ? "gemini-3.6-flash" : geminiModel;
    openaiTranscriptionModel = openaiTranscriptionModel == null || openaiTranscriptionModel.isBlank() ? "gpt-4o-mini-transcribe" : openaiTranscriptionModel;
    openFoodFactsBaseUrl = openFoodFactsBaseUrl == null || openFoodFactsBaseUrl.isBlank()
        ? "https://world.openfoodfacts.org/api/v2" : openFoodFactsBaseUrl;
  }

  public BotProperties(String telegramToken, String webhookSecret, Set<Long> allowedTelegramUserIds,
      String defaultTimezone, String openaiApiKey, String openaiModel) {
    this(telegramToken, webhookSecret, allowedTelegramUserIds, defaultTimezone, openaiApiKey,
        openaiModel, 10, "", "gemini-3.6-flash", "gpt-4o-mini-transcribe", "https://world.openfoodfacts.org/api/v2");
  }
}
