package io.github.foodjournal.repository;

import io.github.foodjournal.domain.*;
import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.Optional;
import org.springframework.data.jpa.repository.*;

public interface JournalChangeSetRepository extends JpaRepository<JournalChangeSet,Long> {
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  Optional<JournalChangeSet> findFirstByUserAndUndoneAtIsNullAndExpiresAtAfterOrderByCreatedAtDescIdDesc(FoodUser user,Instant now);
  void deleteByExpiresAtBefore(Instant now);
}
