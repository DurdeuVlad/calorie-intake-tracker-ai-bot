package io.github.foodjournal.config;

import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("food-journal.frontends")
public record MessagingProperties(Telegram telegram, Mattermost mattermost) {
  public MessagingProperties {
    telegram = telegram == null ? new Telegram(true, Set.of()) : telegram;
    mattermost = mattermost == null ? new Mattermost(false, "", "", "", Set.of()) : mattermost;
  }
  public record Telegram(boolean enabled, Set<String> allowedUserIds) {
    public Telegram { allowedUserIds = allowedUserIds == null ? Set.of() : Set.copyOf(allowedUserIds); }
  }
  public record Mattermost(boolean enabled, String internalUrl, String botToken, String botUserId, Set<String> allowedUserIds) {
    public Mattermost { internalUrl = internalUrl == null ? "" : internalUrl; botToken = botToken == null ? "" : botToken; botUserId = botUserId == null ? "" : botUserId; allowedUserIds = allowedUserIds == null ? Set.of() : Set.copyOf(allowedUserIds); }
  }
}
