package io.github.foodjournal.repository;
import io.github.foodjournal.domain.ProcessedTelegramUpdate; import org.springframework.data.jpa.repository.*; import org.springframework.data.repository.query.Param;
public interface ProcessedTelegramUpdateRepository extends JpaRepository<ProcessedTelegramUpdate,Long>{
  @Modifying
  @Query(value="insert into processed_telegram_updates (update_id, processed_at) values (:updateId, current_timestamp) on conflict (update_id) do nothing", nativeQuery=true)
  int claimIfNew(@Param("updateId") long updateId);
}
