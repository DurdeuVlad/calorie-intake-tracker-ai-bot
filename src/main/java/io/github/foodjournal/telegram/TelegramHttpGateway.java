package io.github.foodjournal.telegram;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties; import io.github.foodjournal.config.BotProperties; import java.net.http.HttpClient; import java.time.Duration; import java.util.Map; import org.springframework.http.client.JdkClientHttpRequestFactory; import org.springframework.stereotype.Component; import org.springframework.web.client.RestClient;
@Component public class TelegramHttpGateway implements TelegramGateway {
 private final RestClient client; private final BotProperties props;
 public TelegramHttpGateway(RestClient.Builder b, BotProperties props){JdkClientHttpRequestFactory factory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());factory.setReadTimeout(Duration.ofSeconds(10));this.client=b.requestFactory(factory).baseUrl("https://api.telegram.org").build();this.props=props;}
 public long sendMessage(long chatId,String text){return call("sendMessage",Map.of("chat_id",chatId,"text",text),true);}
 public void editMessage(long chatId,long messageId,String text){call("editMessageText",Map.of("chat_id",chatId,"message_id",messageId,"text",text),false);}
 public void pinMessage(long chatId,long messageId){call("pinChatMessage",Map.of("chat_id",chatId,"message_id",messageId,"disable_notification",true),false);}
 private long call(String method,Map<String,Object> body,boolean needMessage){TelegramResponse response=client.post().uri("/bot{token}/{method}",props.telegramToken(),method).body(body).retrieve().body(TelegramResponse.class);if(response==null||!response.ok||response.result==null||(needMessage&&response.result.message_id==null))throw new IllegalStateException("Telegram API rejected "+method);return needMessage?response.result.message_id:0L;}
 @JsonIgnoreProperties(ignoreUnknown=true) record TelegramResponse(boolean ok,TelegramResult result){} @JsonIgnoreProperties(ignoreUnknown=true) record TelegramResult(Long message_id){}
}
