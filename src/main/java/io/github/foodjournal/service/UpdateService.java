package io.github.foodjournal.service;
import io.github.foodjournal.config.BotProperties; import io.github.foodjournal.domain.ProcessedTelegramUpdate; import io.github.foodjournal.repository.ProcessedTelegramUpdateRepository; import io.github.foodjournal.telegram.*; import io.github.foodjournal.application.JournalApplicationService; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service public class UpdateService {
 private final BotProperties props; private final ProcessedTelegramUpdateRepository processed; private final TelegramGateway telegram; private final JournalApplicationService journal;
 public UpdateService(BotProperties p,ProcessedTelegramUpdateRepository d,TelegramGateway t,JournalApplicationService j){props=p;processed=d;telegram=t;journal=j;}
 @Transactional public void handle(TelegramUpdate update){
   if(update.update_id()==null || processed.existsById(update.update_id())) return;
   TelegramMessage msg=update.message()!=null?update.message():update.edited_message(); if(msg==null||msg.from()==null||msg.from().id()==null||msg.chat()==null) return;
   long id=msg.from().id(); if(!props.allowedTelegramUserIds().contains(id)) return;
   processed.save(new ProcessedTelegramUpdate(update.update_id()));
   String text=msg.text(); if(text==null||text.isBlank()){ telegram.sendMessage(msg.chat().id(),"I received your media. Media analysis is being configured; no original file was stored."); return; }
   String reply=journal.handle(id,msg.from().first_name(),text.trim()); telegram.sendMessage(msg.chat().id(),reply);
 }
}
