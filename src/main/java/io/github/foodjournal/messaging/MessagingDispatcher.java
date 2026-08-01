package io.github.foodjournal.messaging;

import io.github.foodjournal.domain.MessagingOutboundMessage; import io.github.foodjournal.repository.MessagingOutboundRepository; import org.springframework.scheduling.annotation.Scheduled; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service public class MessagingDispatcher {
 private final MessagingOutboundRepository messages; private final FrontendRegistry frontends;
 public MessagingDispatcher(MessagingOutboundRepository messages,FrontendRegistry frontends){this.messages=messages;this.frontends=frontends;}
 @Scheduled(fixedDelayString="${food-journal.outbox-delay-ms:5000}") @Transactional public void dispatch(){for(MessagingOutboundMessage message:messages.lockReady()){message.claim();try{MessagingFrontend frontend=frontends.require(message.getProvider());String text=fit(message.getText(),frontend.messageLimit());frontend.send(message.getConversationId(),text);message.sent();}catch(Exception failure){message.retry();}}}
 static String fit(String text,int limit){if(text==null)return "";if(text.length()<=limit)return text;String suffix="\n[Message truncated]";if(limit<=suffix.length())return suffix.substring(0,limit);return text.substring(0,limit-suffix.length())+suffix;}
}
