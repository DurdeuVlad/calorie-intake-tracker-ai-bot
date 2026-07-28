package io.github.foodjournal.telegram;
import io.github.foodjournal.config.BotProperties; import io.github.foodjournal.service.UpdateService; import org.springframework.http.*; import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/telegram") public class TelegramWebhookController {
 private final BotProperties props; private final UpdateService service; public TelegramWebhookController(BotProperties p,UpdateService s){props=p;service=s;}
 @PostMapping("/webhook") public ResponseEntity<Void> webhook(@RequestHeader(value="X-Telegram-Bot-Api-Secret-Token",required=false) String secret,@RequestBody TelegramUpdate update){ if(!props.webhookSecret().equals(secret)) return ResponseEntity.status(HttpStatus.FORBIDDEN).build(); service.handle(update); return ResponseEntity.ok().build(); }
}
