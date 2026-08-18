package io.github.foodjournal.infrastructure.openai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import io.github.foodjournal.config.BotProperties;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class OpenAiVoiceTranscriberTest {
  @Test void submitsOggAsMultipartAndReturnsTranscript() {
    RestClient.Builder builder=RestClient.builder().baseUrl("https://api.openai.com/v1"); MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
    server.expect(once(),requestTo("https://api.openai.com/v1/audio/transcriptions")).andExpect(method(org.springframework.http.HttpMethod.POST)).andExpect(header("Authorization","Bearer key")).andExpect(content().contentTypeCompatibleWith(MediaType.MULTIPART_FORM_DATA)).andExpect(content().string(org.hamcrest.Matchers.containsString("gpt-4o-mini-transcribe"))).andExpect(content().string(org.hamcrest.Matchers.containsString("voice.ogg"))).andRespond(withSuccess("{\"text\":\"two eggs\"}",MediaType.APPLICATION_JSON));
    String text=new OpenAiVoiceTranscriber(builder.build(),props()).transcribe(new byte[]{1,2,3},"audio/ogg");
    assertThat(text).isEqualTo("two eggs"); server.verify();
  }
  private BotProperties props(){return new BotProperties("t","s",Set.of(1L),"Europe/Bucharest","key","test");}
}
