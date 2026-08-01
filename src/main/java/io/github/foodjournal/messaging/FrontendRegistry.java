package io.github.foodjournal.messaging;

import java.util.*;
import org.springframework.stereotype.Component;

@Component
public class FrontendRegistry {
  private final Map<String, MessagingFrontend> frontends;
  public FrontendRegistry(List<MessagingFrontend> items) {
    Map<String, MessagingFrontend> found = new HashMap<>();
    for (MessagingFrontend item : items) found.put(item.provider(), item);
    frontends = Map.copyOf(found);
  }
  public Optional<MessagingFrontend> find(String provider) {
    return Optional.ofNullable(frontends.get(provider)).filter(MessagingFrontend::enabled);
  }
  public MessagingFrontend require(String provider) { return find(provider).orElseThrow(() -> new IllegalArgumentException("Messaging frontend is unavailable")); }
}
