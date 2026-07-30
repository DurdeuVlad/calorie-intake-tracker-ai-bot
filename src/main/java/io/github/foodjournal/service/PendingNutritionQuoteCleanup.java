package io.github.foodjournal.service;

import io.github.foodjournal.repository.PendingNutritionQuoteRepository;
import java.time.Instant;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@ConditionalOnProperty(prefix="food-journal", name="scheduling-enabled", havingValue="true", matchIfMissing=true)
public class PendingNutritionQuoteCleanup {
  private final PendingNutritionQuoteRepository quotes;
  public PendingNutritionQuoteCleanup(PendingNutritionQuoteRepository quotes){this.quotes=quotes;}
  @Transactional @Scheduled(fixedDelayString="${food-journal.pending-nutrition-quote-cleanup-delay-ms:900000}")
  public void removeExpiredQuotes(){quotes.deleteByExpiresAtBefore(Instant.now());}
}
