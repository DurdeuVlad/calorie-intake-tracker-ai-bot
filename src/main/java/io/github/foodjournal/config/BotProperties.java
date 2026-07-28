package io.github.foodjournal.config;

import jakarta.validation.constraints.NotBlank;
import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.ConstructorBinding;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("food-journal")
public record BotProperties(
    @NotBlank String telegramToken,
    @NotBlank String webhookSecret,
    Set<Long> allowedTelegramUserIds,
    String defaultTimezone,
    String openaiApiKey,
    String openaiModel,
    String geminiApiKey,
    String openFoodFactsBaseUrl) {
  @ConstructorBinding public BotProperties {
    allowedTelegramUserIds = allowedTelegramUserIds == null ? Set.of() : Set.copyOf(allowedTelegramUserIds);
    defaultTimezone = defaultTimezone == null ? "Europe/Bucharest" : defaultTimezone;
    openaiModel = openaiModel == null ? "gpt-5.4-mini" : openaiModel;
    geminiApiKey = geminiApiKey == null ? "" : geminiApiKey;
    openFoodFactsBaseUrl = openFoodFactsBaseUrl == null || openFoodFactsBaseUrl.isBlank()
        ? "https://world.openfoodfacts.org/api/v2" : openFoodFactsBaseUrl;
  }

  public BotProperties(String telegramToken, String webhookSecret, Set<Long> allowedTelegramUserIds,
      String defaultTimezone, String openaiApiKey, String openaiModel) {
    this(telegramToken, webhookSecret, allowedTelegramUserIds, defaultTimezone, openaiApiKey,
        openaiModel, "", "https://world.openfoodfacts.org/api/v2");
  }
}
