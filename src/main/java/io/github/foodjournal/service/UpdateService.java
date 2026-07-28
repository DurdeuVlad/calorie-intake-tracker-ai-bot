package io.github.foodjournal.service;
import io.github.foodjournal.config.BotProperties; import io.github.foodjournal.domain.OutboundTelegramMessage; import io.github.foodjournal.repository.ProcessedTelegramUpdateRepository; import io.github.foodjournal.repository.OutboundTelegramMessageRepository; import io.github.foodjournal.telegram.*; import io.github.foodjournal.application.JournalApplicationService; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service public class UpdateService {
 private final BotProperties props; private final ProcessedTelegramUpdateRepository processed; private final OutboundTelegramMessageRepository outbound; private final JournalApplicationService journal;
 public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,OutboundTelegramMessageRepository o,JournalApplicationService j){props=p;processed=d;outbound=o;journal=j;}
 @Transactional public void handle(TelegramUpdate update){
   if(update==null || update.update_id()==null) return;
   TelegramMessage msg=update.message()!=null?update.message():update.edited_message(); if(msg==null||msg.from()==null||msg.from().id()==null||msg.chat()==null||msg.chat().id()==null) return;
   long id=msg.from().id(); if(!props.allowedTelegramUserIds().contains(id)) return;
   if(processed.claimIfNew(update.update_id()) == 0) return;
   String text=msg.text(); if(text==null||text.isBlank()){ outbound.save(new OutboundTelegramMessage(msg.chat().id(),"I received your media. Media analysis is being configured; no original file was stored.")); return; }
   String reply=journal.handle(id,msg.chat().id(),msg.from().first_name(),text.trim()); outbound.save(new OutboundTelegramMessage(msg.chat().id(),reply));
 }
}
