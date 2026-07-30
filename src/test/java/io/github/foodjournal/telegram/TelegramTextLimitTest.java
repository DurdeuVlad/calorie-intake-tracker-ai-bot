package io.github.foodjournal.telegram;

import static org.assertj.core.api.Assertions.assertThat;
import org.junit.jupiter.api.Test;

class TelegramTextLimitTest {
  @Test void keepsNormalPlainTextVerbatim(){assertThat(TelegramTextLimit.fit("Ai **642 kcal** <ok> [link](url)")).isEqualTo("Ai **642 kcal** <ok> [link](url)");}
  @Test void capsLongTextAsOneSafeOutboxDelivery(){String result=TelegramTextLimit.fit("a".repeat(5000));assertThat(result).hasSize(TelegramTextLimit.MAX_LENGTH).endsWith("[Message truncated]");}
}
