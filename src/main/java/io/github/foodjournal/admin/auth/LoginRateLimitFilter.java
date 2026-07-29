package io.github.foodjournal.admin.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Optional;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class LoginRateLimitFilter extends OncePerRequestFilter {
  private final LoginAttemptService attempts; private final AdminAuditService audit;
  public LoginRateLimitFilter(LoginAttemptService attempts, AdminAuditService audit) { this.attempts=attempts; this.audit=audit; }
  @Override protected boolean shouldNotFilter(HttpServletRequest request) { return !HttpMethod.POST.matches(request.getMethod()) || !"/login".equals(request.getRequestURI()); }
  @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws IOException, ServletException {
    String key = key(request);
    if (!attempts.isBlocked(key)) { chain.doFilter(request, response); return; }
    audit.record("ANONYMOUS", key, "ADMIN_LOGIN_RATE_LIMITED", "ADMIN_USER", null);
    response.setStatus(429); response.setContentType("application/json"); response.getWriter().write("{\"code\":\"RATE_LIMITED\"}");
  }
  public static String key(HttpServletRequest request) { return Optional.ofNullable(request.getParameter("username")).orElse("unknown").trim().toLowerCase() + "@" + request.getRemoteAddr(); }
}
