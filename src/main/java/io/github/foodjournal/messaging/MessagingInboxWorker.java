package io.github.foodjournal.messaging;

import com.fasterxml.jackson.databind.ObjectMapper; import io.github.foodjournal.application.*; import io.github.foodjournal.config.*; import io.github.foodjournal.domain.*; import io.github.foodjournal.infrastructure.openai.OpenAiVoiceTranscriber; import io.github.foodjournal.repository.*; import java.util.*; import org.springframework.scheduling.annotation.Scheduled; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;

/** Durable provider-neutral message worker. It intentionally never logs private message payloads. */
@Service public class MessagingInboxWorker {
 private final MessagingInboxRepository inbox; private final MessagingIdentityRepository identities; private final MessagingRouteRepository routes; private final MessagingOutboundRepository outbox; private final FoodUserRepository users; private final JournalApplicationService journal; private final MessageLinkService links; private final MessagingProperties properties; private final ObjectMapper json; private final FrontendRegistry frontends; private final FoodMediaExtractor media; private final OpenAiVoiceTranscriber voice; private final MessagingDailyStatusService status;
 public MessagingInboxWorker(MessagingInboxRepository inbox,MessagingIdentityRepository identities,MessagingRouteRepository routes,MessagingOutboundRepository outbox,FoodUserRepository users,JournalApplicationService journal,MessageLinkService links,MessagingProperties properties,ObjectMapper json,FrontendRegistry frontends,FoodMediaExtractor media,OpenAiVoiceTranscriber voice,MessagingDailyStatusService status){this.inbox=inbox;this.identities=identities;this.routes=routes;this.outbox=outbox;this.users=users;this.journal=journal;this.links=links;this.properties=properties;this.json=json;this.frontends=frontends;this.media=media;this.voice=voice;this.status=status;}
 @Scheduled(fixedDelayString="${food-journal.inbox-delay-ms:500}") @Transactional public void dispatch(){for(MessagingInboxMessage row:inbox.lockReady()){row.claim();try{process(json.readValue(row.getPayload(),InboundMessage.class));row.complete(row.getLeaseToken());}catch(Exception failure){row.retry(row.getLeaseToken());}}}
 private void process(InboundMessage message) {
   if (!allowed(message)) return;
   String text=message.text()==null?"":message.text().trim(); String caption=message.caption()==null?"":message.caption().trim();
   if ("telegram".equals(message.provider()) && "/link".equalsIgnoreCase(text)) { FoodUser user=telegramUser(message); reply(message,"Your Mattermost link code is "+links.issue(user)+". Send `link CODE` in a direct message to the Mattermost bot within 10 minutes."); return; }
   if ("mattermost".equals(message.provider()) && text.toLowerCase(Locale.ROOT).startsWith("link ")) { try { links.redeem(text.substring(5).trim().toUpperCase(Locale.ROOT),message.provider(),message.userId(),message.conversationId()); reply(message,"Your existing food journal is linked."); } catch(IllegalArgumentException badCode) { reply(message,"That link code is invalid, expired, or already used."); } return; }
   MessagingIdentity identity=identities.findByProviderAndExternalUserId(message.provider(),message.userId()).orElse(null);
   if(identity==null){ if("telegram".equals(message.provider())) identity=new MessagingIdentity(telegramUser(message),"telegram",message.userId()); else return; identities.save(identity); }
   FoodUser linkedUser=identity.getUser();
   routes.findByUserAndProviderAndConversationId(linkedUser,message.provider(),message.conversationId()).orElseGet(()->routes.save(new MessagingRoute(linkedUser,message.provider(),message.conversationId())));
   if(!message.attachments().isEmpty() && text.isBlank()) { try { Attachment attachment=message.attachments().getFirst(); try(TransientVoicePayload payload=frontends.require(message.provider()).download(attachment)){ text=attachment.kind()==Attachment.Kind.VOICE?voice.transcribe(payload.bytes(),attachment.mimeType()):media.extract(payload.bytes(),attachment.mimeType(),attachment.kind()==Attachment.Kind.PHOTO?FoodMediaType.PHOTO:FoodMediaType.DOCUMENT); } } catch(Exception failure) { reply(message,"I could not analyze that media. Please send clearer media or text."); return; } }
   if(!caption.isBlank()) text=text.isBlank()?caption:text+"\nUser caption: "+caption;
   if(text.isBlank()) return;
   long legacyId=identity.getUser().getTelegramUserId();
   String finalText=text; String response=MessagingExecutionContext.run(()->journal.handle(legacyId,legacyId,message.displayName(),finalText));
   status.refresh(identity.getUser(),message.provider(),message.conversationId());
   reply(message,response);
 }
 private FoodUser telegramUser(InboundMessage message){return users.findByTelegramUserId(Long.parseLong(message.userId())).orElseGet(()->{journal.handle(Long.parseLong(message.userId()),Long.parseLong(message.conversationId()),message.displayName(),"/start");return users.findByTelegramUserId(Long.parseLong(message.userId())).orElseThrow();});}
 private boolean allowed(InboundMessage message){return switch(message.provider()){case "telegram" -> properties.telegram().enabled() && properties.telegram().allowedUserIds().contains(message.userId());case "mattermost" -> properties.mattermost().enabled() && properties.mattermost().allowedUserIds().contains(message.userId());default -> false;};}
 private void reply(InboundMessage message,String text){outbox.save(new MessagingOutboundMessage(message.provider(),message.conversationId(),text));}
}
