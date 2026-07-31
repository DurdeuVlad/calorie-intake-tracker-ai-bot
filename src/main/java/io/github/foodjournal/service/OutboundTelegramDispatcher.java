package io.github.foodjournal.service;
import io.github.foodjournal.telegram.*; import io.github.foodjournal.terminal.TerminalDeliveryGateway; import org.springframework.scheduling.annotation.Scheduled; import org.springframework.stereotype.Service;
/** Required delivery loop; report scheduling must not affect conversational replies. */
@Service public class OutboundTelegramDispatcher {
 private final OutboundTelegramClaimService claims; private final TelegramGateway telegram;
 public OutboundTelegramDispatcher(OutboundTelegramClaimService c,TelegramGateway t){claims=c;telegram=t;}
 @Scheduled(fixedDelayString="${food-journal.outbox-delay-ms:5000}") public void dispatch(){for(OutboundTelegramClaimService.Delivery message:claims.claimBatch()){try{String text=TelegramTextLimit.fit(message.text());if(telegram instanceof TerminalDeliveryGateway terminal)terminal.sendTerminalMessage(message.chatId(),text,message.sourceUpdateId());else telegram.sendMessage(message.chatId(),text);claims.markSent(message.id(),message.leaseToken());}catch(Exception ignored){claims.scheduleRetry(message.id(),message.leaseToken());}}}
}
