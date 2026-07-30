package io.github.foodjournal.telegram;

import static org.assertj.core.api.Assertions.assertThat;
import org.junit.jupiter.api.Test;

class TelegramPlainTextTest {
  @Test void removesUnsupportedModelMarkdownMarkers(){assertThat(TelegramPlainText.normalize("Ai **642 kcal** și `două` mese.")).isEqualTo("Ai 642 kcal și două mese.");}
  @Test void preservesPlainTextNewlinesAndBullets(){assertThat(TelegramPlainText.normalize("Total: 642 kcal\n- crenvuști\n- pui")).contains("\n- crenvuști");}
}
