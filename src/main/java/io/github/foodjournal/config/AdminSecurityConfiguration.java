package io.github.foodjournal.config;

import io.github.foodjournal.admin.api_key.ApiKeyAuthenticationFilter;
import io.github.foodjournal.admin.auth.*;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Optional;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.core.userdetails.*;
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;

@Configuration
@EnableConfigurationProperties(AdminProperties.class)
@EnableMethodSecurity
public class AdminSecurityConfiguration {
  @Bean PasswordEncoder passwordEncoder() { return Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8(); }
  @Bean UserDetailsService adminUserDetailsService(AdminUserRepository users) {
    return email -> users.findByEmailIgnoreCase(email).map(user -> User.withUsername(user.getEmail()).password(user.getPasswordHash()).roles("ADMIN").disabled(!user.isEnabled()).build()).orElseThrow(() -> new UsernameNotFoundException("Invalid credentials"));
  }
  @Bean SecurityFilterChain securityFilterChain(HttpSecurity http, ApiKeyAuthenticationFilter apiKeys, LoginRateLimitFilter rateLimit,
      AdminProperties properties, LoginAttemptService attempts, AdminUserRepository users, AdminAuditService audit) throws Exception {
    http.csrf(csrf -> csrf.ignoringRequestMatchers("/telegram/webhook", "/api/v1/**"))
        .authorizeHttpRequests(auth -> auth.requestMatchers("/telegram/webhook", "/login").permitAll()
            .requestMatchers("/actuator/**").denyAll()
            .requestMatchers("/admin/**").hasRole("ADMIN").requestMatchers("/api/v1/**").hasRole("API_KEY").anyRequest().permitAll())
        .formLogin(login -> login.permitAll().successHandler(successHandler(attempts, users, audit)).failureHandler(failureHandler(attempts, audit)))
        .sessionManagement(session -> session.sessionFixation().migrateSession())
        .headers(headers -> headers.contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'self'; frame-ancestors 'none'; base-uri 'self'"))
            .frameOptions(frame -> frame.deny()).referrerPolicy(Customizer.withDefaults()))
        .addFilterBefore(apiKeys, UsernamePasswordAuthenticationFilter.class)
        .addFilterBefore(rateLimit, UsernamePasswordAuthenticationFilter.class);
    if (properties.requireHttps()) http.requiresChannel(channel -> channel.requestMatchers("/admin/**", "/api/v1/**", "/login").requiresSecure());
    return http.build();
  }
  private AuthenticationFailureHandler failureHandler(LoginAttemptService attempts, AdminAuditService audit) {
    return (request, response, exception) -> { String key = loginKey(request); attempts.failed(key); audit.record("ANONYMOUS", key, "ADMIN_LOGIN_FAILED", "ADMIN_USER", null); response.sendRedirect("/login?error"); };
  }
  private AuthenticationSuccessHandler successHandler(LoginAttemptService attempts, AdminUserRepository users, AdminAuditService audit) {
    return (request, response, authentication) -> { String email = authentication.getName(); attempts.succeeded(loginKey(request)); users.findByEmailIgnoreCase(email).ifPresent(AdminUser::markLoggedIn); audit.record("ADMIN", email, "ADMIN_LOGIN_SUCCEEDED", "ADMIN_USER", email); response.sendRedirect("/admin"); };
  }
  private String loginKey(HttpServletRequest request) { return LoginRateLimitFilter.key(request); }
}
