package io.github.foodjournal;

import io.github.foodjournal.config.BotProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableConfigurationProperties(BotProperties.class)
@EnableScheduling
public class FoodJournalApplication {
  public static void main(String[] args) { SpringApplication.run(FoodJournalApplication.class, args); }
}
