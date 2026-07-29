package io.github.foodjournal.admin.auth;

import io.github.foodjournal.config.AdminProperties;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Service;

/** Local, bounded login throttle. This service intentionally does not retain passwords or request payloads. */
@Service
public class LoginAttemptService {
  private final AdminProperties properties;
  private final ConcurrentHashMap<String, Attempt> attempts = new ConcurrentHashMap<>();
  public LoginAttemptService(AdminProperties properties) { this.properties = properties; }
  public boolean isBlocked(String key) {
    Attempt attempt = attempts.get(key);
    return attempt != null && !attempt.expired(properties) && attempt.failures >= properties.loginMaxAttempts();
  }
  public void failed(String key) { attempts.compute(key, (ignored, current) -> current == null || current.expired(properties) ? new Attempt(1, Instant.now()) : new Attempt(current.failures + 1, current.firstFailure)); }
  public void succeeded(String key) { attempts.remove(key); }
  private record Attempt(int failures, Instant firstFailure) { boolean expired(AdminProperties p) { return firstFailure.plus(p.loginWindow()).isBefore(Instant.now()); } }
}
