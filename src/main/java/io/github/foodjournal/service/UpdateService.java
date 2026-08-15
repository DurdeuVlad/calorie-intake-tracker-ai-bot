package io.github.foodjournal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import io.github.foodjournal.telegram.*;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.Comparator;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service public class UpdateService {
 private static final Logger log=LoggerFactory.getLogger(UpdateService.class);
 private final BotProperties props; private final ProcessedTelegramUpdateRepository processed; private final OutboundTelegramMessageRepository outbound; private final JournalApplicationService journal; private final VoiceTranscriber voice; private final FoodMediaExtractor media; private final FoodUserRepository users; private final ConversationMemoryService memory; private final TelegramInboxUpdateRepository inbox; private final ObjectMapper json; private final MeterRegistry metrics;
 @Autowired public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v,FoodMediaExtractor m,FoodUserRepository users,ConversationMemoryService memory,TelegramInboxUpdateRepository inbox,ObjectMapper json,ObjectProvider<MeterRegistry> metrics){props=p;processed=d;outbound=o;journal=j;voice=v;media=m;this.users=users;this.memory=memory;this.inbox=inbox;this.json=json;this.metrics=metrics.getIfAvailable();}
 public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v,FoodMediaExtractor m,FoodUserRepository users,ConversationMemoryService memory,TelegramInboxUpdateRepository inbox,ObjectMapper json){props=p;processed=d;outbound=o;journal=j;voice=v;media=m;this.users=users;this.memory=memory;this.inbox=inbox;this.json=json;this.metrics=null;}
 public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v,FoodMediaExtractor m){props=p;processed=d;outbound=o;journal=j;voice=v;media=m;this.users=null;this.memory=null;this.inbox=null;this.json=null;this.metrics=null;}
 public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v){this(p,d,o,j,v,(file,mime,type)->{throw new IllegalStateException("Media analysis unavailable");});}

 /** Fast webhook boundary: validates, permanently deduplicates, and persists work only. */
 @Transactional public void enqueue(TelegramUpdate update){TelegramMessage msg=validMessage(update);if(msg==null||inbox==null||json==null)return;if(processed.claimIfNew(update.update_id())==0)return;try{inbox.save(new TelegramInboxUpdate(update.update_id(),msg.from().id(),msg.chat().id(),json.writeValueAsString(update)));}catch(Exception failure){throw new IllegalStateException("Could not enqueue Telegram update",failure);}}
 /** Legacy/direct entry point retained for focused tests; production controller uses enqueue. */
 @Transactional public void handle(TelegramUpdate update){process(update,true,null);}
 @Transactional public void processQueued(TelegramUpdate update,long sourceUpdateId,java.util.UUID leaseToken){if(inbox==null)return;TelegramInboxUpdate row=inbox.lockByUpdateId(sourceUpdateId).orElseThrow();if(row.getStatus()!=TelegramInboxUpdate.Status.IN_PROGRESS||!leaseToken.equals(row.getLeaseToken()))return;process(update,false,sourceUpdateId);row.complete(leaseToken);}
 private void process(TelegramUpdate update,boolean claim,Long sourceUpdateId){
   TelegramMessage msg=validMessage(update);if(msg==null)return;if(claim&&processed.claimIfNew(update.update_id())==0)return;
   String text=msg.text(); if((text==null||text.isBlank())&&msg.voice()!=null){try{text=voice.transcribe(msg.voice().file_id(),msg.voice().mime_type());}catch(Exception failure){logMediaFailure("voice",update.update_id(),msg.chat().id(),failure);reply(msg.chat().id(),voiceFailureReply(msg.from()),sourceUpdateId);return;}}
   if((text==null||text.isBlank())&&msg.photo()!=null&&!msg.photo().isEmpty()){try{TelegramPhoto photo=msg.photo().stream().filter(p->p!=null&&p.file_id()!=null&&!p.file_id().isBlank()).max(Comparator.comparing(p->p.file_size()==null?0:p.file_size())).orElseThrow();text=withCaption(media.extract(photo.file_id(),"image/jpeg",FoodMediaType.PHOTO),msg.caption());}catch(Exception failure){logMediaFailure("photo",update.update_id(),msg.chat().id(),failure);reply(msg.chat().id(),"I could not analyze that photo. Please send a clearer food photo or text.",sourceUpdateId);return;}}
   if((text==null||text.isBlank())&&msg.document()!=null){try{text=withCaption(media.extract(msg.document().file_id(),msg.document().mime_type(),FoodMediaType.DOCUMENT),msg.caption());}catch(Exception failure){logMediaFailure("document",update.update_id(),msg.chat().id(),failure);reply(msg.chat().id(),"I could not analyze that document. Please send a PDF with a food label or use text.",sourceUpdateId);return;}}
   if(text==null||text.isBlank()){reply(msg.chat().id(),"I received your media. No original file was stored.",sourceUpdateId);return;}
   String input=text.trim();String response=(msg.photo()!=null&&!msg.photo().isEmpty()||msg.document()!=null)?journal.handleMediaEvidence(msg.from().id(),msg.chat().id(),msg.from().first_name(),input):journal.handle(msg.from().id(),msg.chat().id(),msg.from().first_name(),input);reply(msg.chat().id(),response,sourceUpdateId);if(memory!=null&&users!=null)users.findByTelegramUserId(msg.from().id()).ifPresent(user->memory.recordTurn(user,input,response));
 }
 private TelegramMessage validMessage(TelegramUpdate update){if(update==null||update.update_id()==null)return null;TelegramMessage msg=update.message()!=null?update.message():update.edited_message();if(msg==null||msg.from()==null||msg.from().id()==null||msg.chat()==null||msg.chat().id()==null)return null;return props.allowedTelegramUserIds().contains(msg.from().id())?msg:null;}
 private String voiceFailureReply(TelegramUser user){return user!=null&&user.language_code()!=null&&user.language_code().toLowerCase(java.util.Locale.ROOT).startsWith("ro")?"Nu am putut transcrie mesajul vocal. Încearcă din nou sau trimite text.":"I could not transcribe that voice note. Please try again or send text.";}
 private void reply(long chatId,String text,Long sourceUpdateId){outbound.save(new OutboundTelegramMessage(chatId,text,sourceUpdateId));} private String withCaption(String extraction,String caption){return caption==null||caption.isBlank()?extraction:extraction+"\nUser caption: "+caption.trim();}

 /** Logs full diagnostic detail (redacted of the bot token) plus a per-category metric, so failures are debuggable from logs/metrics alone without another round of guesswork. */
 private void logMediaFailure(String kind,Long updateId,long chatId,Exception failure){
  String category=failure instanceof MediaProcessingException mediaFailure?mediaFailure.category().name():"UNKNOWN";
  if(metrics!=null)metrics.counter("food_journal_media_failures_total","kind",kind,"category",category).increment();
  log.error("{}_failed update_id={} chat_id={} category={} cause={}",kind,updateId,chatId,category,redact(causeChain(failure)));
 }
 private String causeChain(Throwable failure){StringBuilder chain=new StringBuilder();for(Throwable t=failure;t!=null;t=t.getCause()){if(!chain.isEmpty())chain.append(" <- ");chain.append(t.getClass().getSimpleName()).append(": ").append(t.getMessage());}return chain.toString();}
 private String redact(String message){String token=props.telegramToken();return token==null||token.isBlank()?message:message.replace(token,"***");}
}
