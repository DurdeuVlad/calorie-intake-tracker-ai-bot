package io.github.foodjournal.telegram;

/** Telegram has a 4,096-character text limit. Never split one durable outbox delivery in memory. */
public final class TelegramTextLimit {
  public static final int MAX_LENGTH=4096;
  private static final String SUFFIX="\n[Message truncated]";
  private TelegramTextLimit() {}
  public static String fit(String text){String value=text==null?"":text;return value.length()<=MAX_LENGTH?value:value.substring(0,MAX_LENGTH-SUFFIX.length())+SUFFIX;}
}
