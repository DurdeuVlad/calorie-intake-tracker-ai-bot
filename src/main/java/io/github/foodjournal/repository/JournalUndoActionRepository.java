package io.github.foodjournal.repository;

import io.github.foodjournal.domain.*;
import java.time.Instant;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface JournalUndoActionRepository extends JpaRepository<JournalUndoAction,Long> {
  Optional<JournalUndoAction> findByUserAndExpiresAtAfter(FoodUser user, Instant now);
  void deleteByExpiresAtBefore(Instant now);
}
