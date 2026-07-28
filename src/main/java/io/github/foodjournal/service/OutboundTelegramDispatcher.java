package io.github.foodjournal.service;
import io.github.foodjournal.domain.OutboundTelegramMessage; import io.github.foodjournal.repository.OutboundTelegramMessageRepository; import io.github.foodjournal.telegram.TelegramGateway; import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty; import org.springframework.scheduling.annotation.Scheduled; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service @ConditionalOnProperty(prefix="food-journal", name="scheduling-enabled", havingValue="true", matchIfMissing=true) public class OutboundTelegramDispatcher {
 private final OutboundTelegramMessageRepository messages; private final TelegramGateway telegram;
 public OutboundTelegramDispatcher(OutboundTelegramMessageRepository m,TelegramGateway t){messages=m;telegram=t;}
 @Scheduled(fixedDelayString="${food-journal.outbox-delay-ms:5000}") @Transactional public void dispatch(){ for(OutboundTelegramMessage message:messages.lockReadyForDelivery()){try{telegram.sendMessage(message.getChatId(),message.getText());message.markSent();}catch(Exception ignored){message.scheduleRetry();}} }
}
