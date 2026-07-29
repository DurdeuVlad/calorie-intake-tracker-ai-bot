package io.github.foodjournal.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("food-journal.admin")
public record AdminProperties(
    String bootstrapEmail,
    String bootstrapPassword,
    Boolean requireHttps,
    int loginMaxAttempts,
    Duration loginWindow,
    String traceEncryptionKey,
    int traceRetentionDays) {
  public AdminProperties {
    bootstrapEmail = bootstrapEmail == null ? "" : bootstrapEmail.trim().toLowerCase();
    bootstrapPassword = bootstrapPassword == null ? "" : bootstrapPassword;
    requireHttps = requireHttps == null || requireHttps;
    loginMaxAttempts = loginMaxAttempts <= 0 ? 5 : loginMaxAttempts;
    loginWindow = loginWindow == null || loginWindow.isNegative() || loginWindow.isZero()
        ? Duration.ofMinutes(15) : loginWindow;
    traceEncryptionKey = traceEncryptionKey == null ? "" : traceEncryptionKey.trim();
    traceRetentionDays = traceRetentionDays <= 0 ? 14 : traceRetentionDays;
  }
}
