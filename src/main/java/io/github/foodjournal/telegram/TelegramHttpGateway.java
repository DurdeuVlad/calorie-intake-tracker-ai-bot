package io.github.foodjournal.telegram;
import io.github.foodjournal.config.BotProperties; import java.util.Map; import org.springframework.stereotype.Component; import org.springframework.web.client.RestClient;
@Component public class TelegramHttpGateway implements TelegramGateway {
 private final RestClient client; private final BotProperties props;
 public TelegramHttpGateway(RestClient.Builder b, BotProperties props){this.client=b.baseUrl("https://api.telegram.org").build();this.props=props;}
 public void sendMessage(long chatId,String text){client.post().uri("/bot{token}/sendMessage",props.telegramToken()).body(Map.of("chat_id",chatId,"text",text)).retrieve().toBodilessEntity();}
}
