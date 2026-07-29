package io.github.foodjournal.admin.api_key;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

public enum ApiKeyScope {
  OBSERVABILITY_READ("observability:read"), JOURNAL_EXPORT("journal:export");
  private final String value;
  ApiKeyScope(String value) { this.value = value; }
  public String value() { return value; }
  public static Set<ApiKeyScope> parse(String scopes) {
    if (scopes == null || scopes.isBlank()) return Set.of();
    return Arrays.stream(scopes.split(",")).map(String::trim).filter(s -> !s.isEmpty())
        .map(value -> Arrays.stream(values()).filter(scope -> scope.value.equals(value)).findFirst()
            .orElseThrow(() -> new IllegalArgumentException("Unknown API-key scope")))
        .collect(Collectors.toUnmodifiableSet());
  }
  public static String serialize(Set<ApiKeyScope> scopes) { return scopes.stream().map(ApiKeyScope::value).sorted().collect(Collectors.joining(",")); }
}
