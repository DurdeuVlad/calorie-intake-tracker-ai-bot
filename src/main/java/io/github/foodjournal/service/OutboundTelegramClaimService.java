package io.github.foodjournal.service;
import io.github.foodjournal.domain.OutboundTelegramMessage; import io.github.foodjournal.repository.OutboundTelegramMessageRepository; import java.util.List; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service public class OutboundTelegramClaimService {
 public record Delivery(Long id,long chatId,String text) {}
 private final OutboundTelegramMessageRepository messages;
 public OutboundTelegramClaimService(OutboundTelegramMessageRepository messages){this.messages=messages;}
 @Transactional public List<Delivery> claimBatch(){return messages.lockReadyForDelivery().stream().map(message->{message.claim();return new Delivery(message.getId(),message.getChatId(),message.getText());}).toList();}
 @Transactional public void markSent(Long id){messages.findById(id).filter(message->message.getStatus()==OutboundTelegramMessage.Status.IN_PROGRESS).ifPresent(OutboundTelegramMessage::markSent);}
 @Transactional public void scheduleRetry(Long id){messages.findById(id).filter(message->message.getStatus()==OutboundTelegramMessage.Status.IN_PROGRESS).ifPresent(OutboundTelegramMessage::scheduleRetry);}
}
