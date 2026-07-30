package io.github.foodjournal.telegram;

import static org.assertj.core.api.Assertions.assertThat;
import org.junit.jupiter.api.Test;

class TelegramTextChunksTest {
  @Test void keepsShortTextVerbatim(){assertThat(TelegramTextChunks.split("Ai **642 kcal** <ok> [link](url)")).containsExactly("Ai **642 kcal** <ok> [link](url)");}
  @Test void splitsLongTextWithinTelegramLimitWithoutDroppingCharacters(){String text="a".repeat(4096)+"\n"+"b".repeat(4096);var chunks=TelegramTextChunks.split(text);assertThat(chunks).allMatch(chunk->chunk.length()<=4096);assertThat(String.join("",chunks)).isEqualTo(text);}
}
