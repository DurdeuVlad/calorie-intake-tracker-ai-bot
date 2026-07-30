package io.github.foodjournal.telegram;

/** Telegram requests intentionally omit parse_mode, so strip common model markup before delivery. */
final class TelegramPlainText {
  private TelegramPlainText() {}
  static String normalize(String text) {
    if (text == null) return "";
    return text.replace("**", "").replace("__", "").replace("`", "");
  }
}
