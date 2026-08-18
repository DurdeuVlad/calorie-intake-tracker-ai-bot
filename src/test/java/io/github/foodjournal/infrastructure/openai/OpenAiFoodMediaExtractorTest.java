package io.github.foodjournal.infrastructure.openai;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.http.*;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class OpenAiFoodMediaExtractorTest {
  @Test void extractsPhotoEvidenceThroughResponsesApi(){
    RestClient.Builder builder=RestClient.builder().baseUrl("https://api.openai.com/v1");MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
    server.expect(once(),requestTo("https://api.openai.com/v1/responses")).andExpect(header("Authorization","Bearer key")).andExpect(jsonPath("$.model").value("test-model")).andExpect(jsonPath("$.input[0].content[1].type").value("input_image")).andExpect(content().string(org.hamcrest.Matchers.containsString("data:image/jpeg;base64,AQID"))).andRespond(withSuccess("{\"output\":[{\"type\":\"message\",\"content\":[{\"type\":\"output_text\",\"text\":\"Oat bar, 180 kcal\"}]}]}",MediaType.APPLICATION_JSON));
    OpenAiFoodMediaExtractor extractor=new OpenAiFoodMediaExtractor(builder.build(),props());
    assertThat(extractor.extract(new byte[]{1,2,3},"image/jpeg",FoodMediaType.PHOTO)).isEqualTo("Oat bar, 180 kcal");server.verify();
  }
  @Test void sendsPdfAsAnInputFile(){
    RestClient.Builder builder=RestClient.builder().baseUrl("https://api.openai.com/v1");MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
    server.expect(once(),requestTo("https://api.openai.com/v1/responses")).andExpect(jsonPath("$.input[0].content[1].type").value("input_file")).andExpect(jsonPath("$.input[0].content[1].filename").value("document.pdf")).andExpect(content().string(org.hamcrest.Matchers.containsString("data:application/pdf;base64,BAUG"))).andRespond(withSuccess("{\"output\":[{\"content\":[{\"type\":\"output_text\",\"text\":\"Cereal, 120 kcal\"}]}]}",MediaType.APPLICATION_JSON));
    assertThat(new OpenAiFoodMediaExtractor(builder.build(),props()).extract(new byte[]{4,5,6},"application/pdf",FoodMediaType.DOCUMENT)).isEqualTo("Cereal, 120 kcal");server.verify();
  }
  @Test void rejectsUnsupportedDocumentsBeforeCallingOpenAi(){
    RestClient.Builder builder=RestClient.builder().baseUrl("https://api.openai.com/v1");MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
    assertThatThrownBy(()->new OpenAiFoodMediaExtractor(builder.build(),props()).extract(new byte[]{1},"text/plain",FoodMediaType.DOCUMENT)).isInstanceOfSatisfying(MediaProcessingException.class,e->assertThat(e.category()).isEqualTo(MediaProcessingException.Category.INVALID_MEDIA));
    server.verify();
  }
  private BotProperties props(){return new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","key","test-model");}
}
