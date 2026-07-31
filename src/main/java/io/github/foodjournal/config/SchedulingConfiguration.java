package io.github.foodjournal.config;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/** Optional background scheduling; terminal mode drives the inbox and outbox synchronously. */
@Configuration
@EnableScheduling
@ConditionalOnProperty(prefix = "food-journal", name = "scheduling-enabled", havingValue = "true", matchIfMissing = true)
public class SchedulingConfiguration {}
