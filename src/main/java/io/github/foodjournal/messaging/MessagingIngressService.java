package io.github.foodjournal.messaging;

import com.fasterxml.jackson.databind.ObjectMapper; import io.github.foodjournal.domain.MessagingInboxMessage; import io.github.foodjournal.repository.MessagingInboxRepository; import org.springframework.dao.DataIntegrityViolationException; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;

@Service public class MessagingIngressService {
 private final MessagingInboxRepository inbox; private final ObjectMapper json;
 public MessagingIngressService(MessagingInboxRepository inbox,ObjectMapper json){this.inbox=inbox;this.json=json;}
 @Transactional public void accept(InboundMessage message){try{inbox.save(new MessagingInboxMessage(message.provider(),message.eventId(),json.writeValueAsString(message)));}catch(DataIntegrityViolationException duplicate){/* at-least-once provider delivery */}catch(Exception failure){throw new IllegalStateException("Could not persist inbound message",failure);}}
}
