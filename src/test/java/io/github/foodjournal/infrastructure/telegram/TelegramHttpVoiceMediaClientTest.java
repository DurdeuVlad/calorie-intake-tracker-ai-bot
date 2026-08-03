package io.github.foodjournal.infrastructure.telegram;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.http.*;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class TelegramHttpVoiceMediaClientTest {
  @Test void downloadsOnlyTheResolvedTelegramFile(){RestClient.Builder builder=RestClient.builder().baseUrl("https://api.telegram.org");MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();server.expect(once(),requestTo("https://api.telegram.org/bot/token/getFile?file_id=voice-42")).andRespond(withSuccess("{\"ok\":true,\"result\":{\"file_path\":\"voice/file.oga\"}}",MediaType.APPLICATION_JSON));server.expect(once(),requestTo("https://api.telegram.org/file/bottoken/voice%2Ffile.oga")).andRespond(withSuccess(new byte[]{1,2,3},MediaType.APPLICATION_OCTET_STREAM));try(TransientVoicePayload payload=new TelegramHttpVoiceMediaClient(builder.build(),props()).download("voice-42")){assertThat(payload.bytes()).containsExactly(1,2,3);}server.verify();}
  @Test void mapsHttpFailuresWithoutExposingIdentifiers(){RestClient.Builder builder=RestClient.builder().baseUrl("https://api.telegram.org");MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();server.expect(once(),requestTo("https://api.telegram.org/bot/token/getFile?file_id=voice-42")).andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));assertThatThrownBy(()->new TelegramHttpVoiceMediaClient(builder.build(),props()).download("voice-42")).isInstanceOfSatisfying(MediaProcessingException.class,e->{assertThat(e.category()).isEqualTo(MediaProcessingException.Category.TELEGRAM_DOWNLOAD);assertThat(e.getMessage()).doesNotContain("voice-42","token");});server.verify();}
  private BotProperties props(){return new BotProperties("token","secret",Set.of(1L),"Europe/Bucharest","","");}
}
