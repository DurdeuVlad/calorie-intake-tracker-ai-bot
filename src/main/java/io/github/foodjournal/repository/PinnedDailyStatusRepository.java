package io.github.foodjournal.repository;
import io.github.foodjournal.domain.*; import java.util.*; import org.springframework.data.jpa.repository.*;
public interface PinnedDailyStatusRepository extends JpaRepository<PinnedDailyStatus,Long>{
  Optional<PinnedDailyStatus> findByUserAndChatId(FoodUser user,long chatId);
  @Query("select s from PinnedDailyStatus s where s.desiredVersion > s.deliveredVersion order by s.id") List<PinnedDailyStatus> findPending();
}
