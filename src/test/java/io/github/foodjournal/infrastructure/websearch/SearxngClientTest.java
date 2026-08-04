package io.github.foodjournal.infrastructure.websearch;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class SearxngClientTest {
 @Test void readsAndCapsResultsFromTheJsonSearchApi() {
  RestClient.Builder builder=RestClient.builder().baseUrl("https://searxng.example.internal"); MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
  StringBuilder results=new StringBuilder();
  for(int i=1;i<=7;i++){if(i>1)results.append(",");results.append("{\"title\":\"Result "+i+"\",\"url\":\"https://example.com/"+i+"\",\"content\":\"snippet "+i+"\"}");}
  server.expect(once(),requestTo("https://searxng.example.internal/search?q=taco%20bell%20burrito%20calories&format=json")).andRespond(withSuccess("{\"results\":["+results+"]}",MediaType.APPLICATION_JSON));
  var results2=new SearxngClient(builder.build()).search("taco bell burrito calories");
  assertThat(results2).hasSize(5);assertThat(results2.getFirst().title()).isEqualTo("Result 1");assertThat(results2.getFirst().url()).isEqualTo("https://example.com/1");assertThat(results2.getFirst().snippet()).isEqualTo("snippet 1");server.verify();
 }
 @Test void returnsNoResultsWhenDisabledOrBlankQuery(){assertThat(new SearxngClient(null).search("burrito")).isEmpty();}
 @Test void returnsNoResultsOnProviderFailure(){assertThat(new SearxngClient(RestClient.create()).search("burrito")).isEmpty();}
}
