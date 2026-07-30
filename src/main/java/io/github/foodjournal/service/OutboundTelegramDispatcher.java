package io.github.foodjournal.service;
import io.github.foodjournal.telegram.*; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.scheduling.annotation.Scheduled; import org.springframework.stereotype.Service;
@Service @ConditionalOnProperty(prefix="food-journal", name="scheduling-enabled", havingValue="true", matchIfMissing=true) public class OutboundTelegramDispatcher {
 private final OutboundTelegramClaimService claims; private final TelegramGateway telegram;
 public OutboundTelegramDispatcher(OutboundTelegramClaimService c,TelegramGateway t){claims=c;telegram=t;}
 @Scheduled(fixedDelayString="${food-journal.outbox-delay-ms:5000}") public void dispatch(){for(OutboundTelegramClaimService.Delivery message:claims.claimBatch()){try{for(String chunk:TelegramTextChunks.split(message.text()))telegram.sendMessage(message.chatId(),chunk);claims.markSent(message.id(),message.leaseToken());}catch(Exception ignored){claims.scheduleRetry(message.id(),message.leaseToken());}}}
}
