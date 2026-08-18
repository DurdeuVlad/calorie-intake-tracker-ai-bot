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
    String openaiTranscriptionModel,
    String openFoodFactsBaseUrl,
    String searxngBaseUrl,
    String browserlessBaseUrl,
    String browserlessToken) {
  @ConstructorBinding public BotProperties {
    telegramToken = telegramToken == null ? "" : telegramToken;
    webhookSecret = webhookSecret == null ? "" : webhookSecret;
    allowedTelegramUserIds = allowedTelegramUserIds == null ? Set.of() : Set.copyOf(allowedTelegramUserIds);
    defaultTimezone = defaultTimezone == null ? "Europe/Bucharest" : defaultTimezone;
    openaiModel = openaiModel == null ? "gpt-5.6-luna" : openaiModel;
    agentMaxToolCalls = agentMaxToolCalls <= 0 ? 10 : Math.min(agentMaxToolCalls, 10);
    openaiTranscriptionModel = openaiTranscriptionModel == null || openaiTranscriptionModel.isBlank() ? "gpt-4o-mini-transcribe" : openaiTranscriptionModel;
    openFoodFactsBaseUrl = openFoodFactsBaseUrl == null || openFoodFactsBaseUrl.isBlank()
        ? "https://world.openfoodfacts.org/api/v2" : openFoodFactsBaseUrl;
    searxngBaseUrl = searxngBaseUrl == null ? "" : searxngBaseUrl;
    browserlessBaseUrl = browserlessBaseUrl == null ? "" : browserlessBaseUrl;
    browserlessToken = browserlessToken == null ? "" : browserlessToken;
  }

  public BotProperties(String telegramToken, String webhookSecret, Set<Long> allowedTelegramUserIds,
      String defaultTimezone, String openaiApiKey, String openaiModel) {
    this(telegramToken, webhookSecret, allowedTelegramUserIds, defaultTimezone, openaiApiKey,
        openaiModel, 10, "gpt-4o-mini-transcribe", "https://world.openfoodfacts.org/api/v2", "", "", "");
  }
}
