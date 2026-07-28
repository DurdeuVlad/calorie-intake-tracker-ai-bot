package io.github.foodjournal.config;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.FoodJournalApplication;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContextInitializer;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.core.env.SystemEnvironmentPropertySource;

@SpringBootTest(classes = FoodJournalApplication.class, properties = {
    "spring.flyway.enabled=false", "spring.jpa.hibernate.ddl-auto=none",
    "food-journal.scheduling-enabled=false"})
@ContextConfiguration(initializers = ConfigurationEnvironmentBindingTest.EnvironmentVariables.class)
class ConfigurationEnvironmentBindingTest {
  @Autowired BotProperties properties;

  @Test void bindsDocumentedEnvironmentVariables() {
    assertThat(properties.telegramToken()).isEqualTo("telegram-token");
    assertThat(properties.webhookSecret()).isEqualTo("webhook-secret");
    assertThat(properties.allowedTelegramUserIds()).containsExactlyInAnyOrder(101L, 202L);
    assertThat(properties.defaultTimezone()).isEqualTo("Europe/Lisbon");
    assertThat(properties.openaiApiKey()).isEqualTo("openai-key");
    assertThat(properties.openaiModel()).isEqualTo("test-model");
    assertThat(properties.geminiApiKey()).isEqualTo("gemini-key");
    assertThat(properties.openFoodFactsBaseUrl()).isEqualTo("https://foods.example/api/v2");
  }

  static class EnvironmentVariables implements ApplicationContextInitializer<ConfigurableApplicationContext> {
    @Override public void initialize(ConfigurableApplicationContext context) {
      context.getEnvironment().getPropertySources().addFirst(new SystemEnvironmentPropertySource("test-env", Map.ofEntries(
          Map.entry("DATABASE_URL", "jdbc:h2:mem:configuration;MODE=PostgreSQL;DB_CLOSE_DELAY=-1"),
          Map.entry("DATABASE_USERNAME", "sa"), Map.entry("DATABASE_PASSWORD", ""),
          Map.entry("TELEGRAM_BOT_TOKEN", "telegram-token"), Map.entry("TELEGRAM_WEBHOOK_SECRET", "webhook-secret"),
          Map.entry("ALLOWED_TELEGRAM_USER_IDS", "101,202"), Map.entry("DEFAULT_TIMEZONE", "Europe/Lisbon"),
          Map.entry("OPENAI_API_KEY", "openai-key"), Map.entry("OPENAI_MODEL", "test-model"),
          Map.entry("GEMINI_API_KEY", "gemini-key"),
          Map.entry("OPEN_FOOD_FACTS_BASE_URL", "https://foods.example/api/v2"))));
    }
  }
}
