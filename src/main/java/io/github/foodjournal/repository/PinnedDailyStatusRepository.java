package io.github.foodjournal.repository;
import io.github.foodjournal.domain.*; import java.util.*; import org.springframework.data.jpa.repository.*;
public interface PinnedDailyStatusRepository extends JpaRepository<PinnedDailyStatus,Long>{
  Optional<PinnedDailyStatus> findByUserAndChatId(FoodUser user,long chatId);
  @Query(value="select * from pinned_daily_status where desired_version > delivered_version and (status='PENDING' or (status='IN_PROGRESS' and lease_expires_at <= current_timestamp)) order by id for update skip locked limit 1",nativeQuery=true) List<PinnedDailyStatus> lockPending();
}
