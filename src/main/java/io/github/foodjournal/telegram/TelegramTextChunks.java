package io.github.foodjournal.telegram;

import java.util.*;

/** Splits plain Telegram text without changing its content. */
public final class TelegramTextChunks {
  public static final int MAX_LENGTH=4096;
  private TelegramTextChunks() {}
  public static List<String> split(String text){
    String value=text==null?"":text; if(value.length()<=MAX_LENGTH)return List.of(value);
    List<String> chunks=new ArrayList<>();int start=0;while(start<value.length()){int end=Math.min(value.length(),start+MAX_LENGTH);if(end<value.length()){int breakAt=Math.max(value.lastIndexOf('\n',end),value.lastIndexOf(' ',end));if(breakAt>start&&breakAt<end)end=breakAt+1;}chunks.add(value.substring(start,end));start=end;}return List.copyOf(chunks);
  }
}
