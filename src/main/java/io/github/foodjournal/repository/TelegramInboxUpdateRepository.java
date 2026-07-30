package io.github.foodjournal.repository;

import io.github.foodjournal.domain.TelegramInboxUpdate;
import java.util.*;
import org.springframework.data.jpa.repository.*;

public interface TelegramInboxUpdateRepository extends JpaRepository<TelegramInboxUpdate,Long> {
  @Query(value="""
      select * from telegram_update_inbox candidate
      where ((candidate.status = 'PENDING' and candidate.next_attempt_at <= current_timestamp)
          or (candidate.status = 'IN_PROGRESS' and candidate.lease_expires_at <= current_timestamp))
        and not exists (select 1 from telegram_update_inbox earlier
          where earlier.telegram_user_id = candidate.telegram_user_id
            and earlier.update_id < candidate.update_id
            and earlier.status in ('PENDING','IN_PROGRESS'))
      order by candidate.update_id for update skip locked limit 1
      """, nativeQuery=true)
  List<TelegramInboxUpdate> lockNextReady();
}
