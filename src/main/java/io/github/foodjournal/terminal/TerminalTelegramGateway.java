package io.github.foodjournal.terminal;

import io.github.foodjournal.telegram.TelegramGateway;
import java.time.Duration;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.Map;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** Local replacement for Telegram's HTTP API. The runner owns terminal rendering. */
@Component @Profile("terminal")
public class TerminalTelegramGateway implements TelegramGateway, TerminalDeliveryGateway {
  public record Delivery(long chatId, String text, Long sourceUpdateId) {}
  private final BlockingQueue<Delivery> deliveries = new LinkedBlockingQueue<>();
  private final Map<Long,Delivery> delayed = new ConcurrentHashMap<>();

  @Override public long sendMessage(long chatId, String text) { return sendTerminalMessage(chatId,text,null); }
  @Override public long sendTerminalMessage(long chatId, String text, Long sourceUpdateId) { deliveries.add(new Delivery(chatId, text, sourceUpdateId)); return deliveries.size(); }
  @Override public void editMessage(long chatId, long messageId, String text) { deliveries.add(new Delivery(chatId, text, null)); }
  @Override public void pinMessage(long chatId, long messageId) {}
  public Delivery await(long sourceUpdateId, Duration timeout) throws InterruptedException {
    Delivery saved=delayed.remove(sourceUpdateId); if(saved!=null)return saved;
    long deadline=System.nanoTime()+timeout.toNanos();
    while (true) { long remaining=deadline-System.nanoTime(); if(remaining<=0)return null; Delivery delivery=deliveries.poll(remaining,TimeUnit.NANOSECONDS); if(delivery==null)return null; if(Long.valueOf(sourceUpdateId).equals(delivery.sourceUpdateId()))return delivery; if(delivery.sourceUpdateId()!=null)delayed.put(delivery.sourceUpdateId(),delivery); }
  }
}
