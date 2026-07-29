package io.github.foodjournal.application;

import io.github.foodjournal.domain.FoodUser;
import java.time.Instant;

public record AgentContext(FoodUser user, long chatId, boolean romanian, String message, Instant startedAt) {
  public AgentContext(FoodUser user, long chatId, boolean romanian, String message) { this(user, chatId, romanian, message, Instant.now()); }
}
