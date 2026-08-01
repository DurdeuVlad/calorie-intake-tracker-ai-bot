package io.github.foodjournal;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.config.MessagingProperties;
import io.github.foodjournal.terminal.TerminalProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({BotProperties.class, TerminalProperties.class, MessagingProperties.class})
public class FoodJournalApplication {
  public static void main(String[] args) { SpringApplication.run(FoodJournalApplication.class, args); }
}
