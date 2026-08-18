package io.github.foodjournal.config;

import java.net.http.HttpClient;
import java.time.Duration;
import org.springframework.boot.web.client.RestClientCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;

/** Applies a connect/read timeout to every outbound RestClient so a hanging provider cannot hold a DB connection or lock indefinitely. */
@Configuration
public class HttpClientConfiguration {
  @Bean
  public RestClientCustomizer timeoutCustomizer() {
    return builder -> {
      JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());
      factory.setReadTimeout(Duration.ofSeconds(30));
      builder.requestFactory(factory);
    };
  }
}
