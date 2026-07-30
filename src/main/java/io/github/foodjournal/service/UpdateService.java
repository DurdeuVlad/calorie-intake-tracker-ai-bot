package io.github.foodjournal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.application.*;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import io.github.foodjournal.telegram.*;
import java.util.Comparator;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service public class UpdateService {
 private final BotProperties props; private final ProcessedTelegramUpdateRepository processed; private final OutboundTelegramMessageRepository outbound; private final JournalApplicationService journal; private final VoiceTranscriber voice; private final FoodMediaExtractor media; private final FoodUserRepository users; private final ConversationMemoryService memory; private final TelegramInboxUpdateRepository inbox; private final ObjectMapper json;
 @Autowired public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v,FoodMediaExtractor m,FoodUserRepository users,ConversationMemoryService memory,TelegramInboxUpdateRepository inbox,ObjectMapper json){props=p;processed=d;outbound=o;journal=j;voice=v;media=m;this.users=users;this.memory=memory;this.inbox=inbox;this.json=json;}
 public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v,FoodMediaExtractor m){this(p,d,o,j,v,m,null,null,null,null);} public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j,VoiceTranscriber v){this(p,d,o,j,v,(file,mime,type)->{throw new IllegalStateException("Media analysis unavailable");},null,null,null,null);}

 /** Fast webhook boundary: validates, permanently deduplicates, and persists work only. */
 @Transactional public void enqueue(TelegramUpdate update){TelegramMessage msg=validMessage(update);if(msg==null||inbox==null||json==null)return;if(processed.claimIfNew(update.update_id())==0)return;try{inbox.save(new TelegramInboxUpdate(update.update_id(),msg.from().id(),msg.chat().id(),json.writeValueAsString(update)));}catch(Exception failure){throw new IllegalStateException("Could not enqueue Telegram update",failure);}}
 /** Legacy/direct entry point retained for focused tests; production controller uses enqueue. */
 @Transactional public void handle(TelegramUpdate update){process(update,true,null);}
 @Transactional public void processQueued(TelegramUpdate update,long sourceUpdateId,java.util.UUID leaseToken){if(inbox==null)return;TelegramInboxUpdate row=inbox.lockByUpdateId(sourceUpdateId).orElseThrow();if(row.getStatus()!=TelegramInboxUpdate.Status.IN_PROGRESS||!leaseToken.equals(row.getLeaseToken()))return;process(update,false,sourceUpdateId);row.complete(leaseToken);}
 private void process(TelegramUpdate update,boolean claim,Long sourceUpdateId){
   TelegramMessage msg=validMessage(update);if(msg==null)return;if(claim&&processed.claimIfNew(update.update_id())==0)return;
   String text=msg.text(); if((text==null||text.isBlank())&&msg.voice()!=null){try{text=voice.transcribe(msg.voice().file_id(),msg.voice().mime_type());}catch(Exception failure){reply(msg.chat().id(),"I could not transcribe that voice note. Please try again or send text.",sourceUpdateId);return;}}
   if((text==null||text.isBlank())&&msg.photo()!=null&&!msg.photo().isEmpty()){try{TelegramPhoto photo=msg.photo().stream().filter(p->p!=null&&p.file_id()!=null&&!p.file_id().isBlank()).max(Comparator.comparing(p->p.file_size()==null?0:p.file_size())).orElseThrow();text=withCaption(media.extract(photo.file_id(),"image/jpeg",FoodMediaType.PHOTO),msg.caption());}catch(Exception failure){reply(msg.chat().id(),"I could not analyze that photo. Please send a clearer food photo or text.",sourceUpdateId);return;}}
   if((text==null||text.isBlank())&&msg.document()!=null){try{text=withCaption(media.extract(msg.document().file_id(),msg.document().mime_type(),FoodMediaType.DOCUMENT),msg.caption());}catch(Exception failure){reply(msg.chat().id(),"I could not analyze that document. Please send a PDF with a food label or use text.",sourceUpdateId);return;}}
   if(text==null||text.isBlank()){reply(msg.chat().id(),"I received your media. No original file was stored.",sourceUpdateId);return;}
   String input=text.trim();String response=(msg.photo()!=null&&!msg.photo().isEmpty()||msg.document()!=null)?journal.handleMediaEvidence(msg.from().id(),msg.chat().id(),msg.from().first_name(),input):journal.handle(msg.from().id(),msg.chat().id(),msg.from().first_name(),input);reply(msg.chat().id(),response,sourceUpdateId);if(memory!=null&&users!=null)users.findByTelegramUserId(msg.from().id()).ifPresent(user->memory.recordTurn(user,input,response));
 }
 private TelegramMessage validMessage(TelegramUpdate update){if(update==null||update.update_id()==null)return null;TelegramMessage msg=update.message()!=null?update.message():update.edited_message();if(msg==null||msg.from()==null||msg.from().id()==null||msg.chat()==null||msg.chat().id()==null)return null;return props.allowedTelegramUserIds().contains(msg.from().id())?msg:null;}
 private void reply(long chatId,String text,Long sourceUpdateId){outbound.save(new OutboundTelegramMessage(chatId,text,sourceUpdateId));} private String withCaption(String extraction,String caption){return caption==null||caption.isBlank()?extraction:extraction+"\nUser caption: "+caption.trim();}
}
