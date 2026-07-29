package io.github.foodjournal.repository;

import io.github.foodjournal.domain.*;
import java.time.Instant;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PendingFoodDraftRepository extends JpaRepository<PendingFoodDraft,Long>{ Optional<PendingFoodDraft> findByUserAndExpiresAtAfter(FoodUser user, Instant now); void deleteByUser(FoodUser user); }
