package io.github.foodjournal.admin.api_key;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class ApiKeyAuthenticationFilter extends OncePerRequestFilter {
  public static final String HEADER = "X-API-Key";
  private final ApiKeyService keys;
  public ApiKeyAuthenticationFilter(ApiKeyService keys) { this.keys = keys; }
  @Override protected boolean shouldNotFilter(HttpServletRequest request) { return !request.getRequestURI().startsWith("/api/v1/"); }
  @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws IOException, ServletException {
    String apiKey = extract(request);
    if (apiKey == null) { unauthorized(response); return; }
    var principal = keys.authenticate(apiKey);
    if (principal.isEmpty()) { unauthorized(response); return; }
    List<SimpleGrantedAuthority> authorities = new java.util.ArrayList<>();
    authorities.add(new SimpleGrantedAuthority("ROLE_API_KEY"));
    principal.get().scopes().forEach(scope -> authorities.add(new SimpleGrantedAuthority("SCOPE_" + scope.value())));
    SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(principal.get(), null, authorities));
    chain.doFilter(request, response);
  }
  private String extract(HttpServletRequest request) {
    String explicit = request.getHeader(HEADER);
    String authorization = request.getHeader(HttpHeaders.AUTHORIZATION);
    String bearer = authorization != null && authorization.regionMatches(true, 0, "Bearer ", 0, 7) ? authorization.substring(7).trim() : null;
    if (explicit != null && !explicit.isBlank() && bearer != null && !bearer.isBlank() && !explicit.equals(bearer)) return null;
    String candidate = explicit != null && !explicit.isBlank() ? explicit.trim() : bearer;
    return candidate == null || candidate.isBlank() ? null : candidate;
  }
  private void unauthorized(HttpServletResponse response) throws IOException { response.setStatus(HttpServletResponse.SC_UNAUTHORIZED); response.setContentType("application/json"); response.getWriter().write("{\"code\":\"UNAUTHORIZED\"}"); }
}
