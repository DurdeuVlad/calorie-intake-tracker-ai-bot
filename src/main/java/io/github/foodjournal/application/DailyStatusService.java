package io.github.foodjournal.application;
import io.github.foodjournal.domain.*; import io.github.foodjournal.repository.*; import java.time.*; import java.util.*; import org.springframework.stereotype.Service; import org.springframework.transaction.annotation.Transactional;
@Service public class DailyStatusService {
 private final UserSettingsRepository settings; private final FoodEntryRepository entries; private final PinnedDailyStatusRepository statuses;
 public DailyStatusService(UserSettingsRepository s,FoodEntryRepository e,PinnedDailyStatusRepository p){settings=s;entries=e;statuses=p;}
 @Transactional public void refresh(FoodUser user,long chatId){UserSettings s=settings.findById(user.getId()).orElseThrow();ZoneId zone=ZoneId.of(s.getTimezone());LocalDate today=LocalDate.now(zone);List<FoodEntry> rows=entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(user,today.atStartOfDay(zone).toInstant(),today.plusDays(1).atStartOfDay(zone).toInstant());int calories=rows.stream().map(FoodEntry::getCalories).filter(Objects::nonNull).mapToInt(Integer::intValue).sum();String text="Today: "+rows.size()+" entries, "+calories+" kcal logged."+(s.getCalorieTarget()==null?"":" Target: "+s.getCalorieTarget()+" kcal.");statuses.findByUserAndChatId(user,chatId).ifPresentOrElse(status->status.request(today,text),()->statuses.save(new PinnedDailyStatus(user,chatId,today,text)));}
 @Transactional public Delivery claim(){return statuses.lockPending().stream().findFirst().map(status->{status.claim();return new Delivery(status.getId(),status.getChatId(),status.getDesiredText(),status.getDesiredVersion(),status.getTelegramMessageId(),status.getLeaseToken());}).orElse(null);}
 @Transactional public void markDelivered(Long id,long version,java.util.UUID token,Long messageId){statuses.findById(id).ifPresent(status->status.delivered(version,token,messageId));}
 @Transactional public void retry(Long id,java.util.UUID token){statuses.findById(id).ifPresent(status->status.retry(token));}
 public record Delivery(Long id,long chatId,String text,long version,Long messageId,java.util.UUID leaseToken){}
}
