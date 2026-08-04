package io.github.foodjournal.infrastructure.websearch;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class BrowserlessClientTest {
 @Test void extractsPlainTextFromRenderedHtml() {
  RestClient.Builder builder=RestClient.builder().baseUrl("https://browserless.example.internal"); MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
  server.expect(once(),requestTo("https://browserless.example.internal/content?token=secret")).andRespond(withSuccess("<html><head><style>.x{}</style></head><body><script>evil()</script><h1>Burrito Supreme</h1><p>710&nbsp;calories</p></body></html>",MediaType.TEXT_HTML));
  var text=new BrowserlessClient(builder.build(),"secret").fetchText("https://taco-example.com/menu");
  assertThat(text).isPresent();assertThat(text.get()).contains("Burrito Supreme").contains("710 calories").doesNotContain("evil()").doesNotContain("<h1>");server.verify();
 }
 @Test void returnsEmptyWhenDisabledOrBlankUrl(){assertThat(new BrowserlessClient(null,"secret").fetchText("https://example.com")).isEmpty();}
 @Test void returnsEmptyOnProviderFailure(){assertThat(new BrowserlessClient(RestClient.create(),null).fetchText("https://example.com")).isEmpty();}
}
