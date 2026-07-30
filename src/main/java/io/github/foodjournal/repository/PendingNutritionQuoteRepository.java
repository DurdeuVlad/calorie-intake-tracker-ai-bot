package io.github.foodjournal.repository;

import io.github.foodjournal.domain.*;
import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.*;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;

public interface PendingNutritionQuoteRepository extends JpaRepository<PendingNutritionQuote, UUID> {
  List<PendingNutritionQuote> findByUserAndExpiresAtAfterOrderByCreatedAtAsc(FoodUser user, Instant now);
  void deleteByExpiresAtBefore(Instant now);
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("select q from PendingNutritionQuote q where q.id=:id and q.user=:user and q.expiresAt>:now")
  Optional<PendingNutritionQuote> lockOwnedActive(@Param("id") UUID id, @Param("user") FoodUser user, @Param("now") Instant now);
}
