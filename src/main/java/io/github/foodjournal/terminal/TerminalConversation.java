package io.github.foodjournal.terminal;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.service.OutboundTelegramDispatcher;
import io.github.foodjournal.service.TelegramInboxWorker;
import io.github.foodjournal.service.UpdateService;
import io.github.foodjournal.telegram.*;
import java.time.Duration;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** Sends a synthetic text update through the normal durable inbox and outbox path. */
@Component @Profile("terminal")
public class TerminalConversation {
  public record Result(String reply, TerminalTraceCollector.Trace trace) {}
  private static final Duration REPLY_TIMEOUT = Duration.ofSeconds(45);
  private final UpdateService updates; private final TelegramInboxWorker inbox; private final OutboundTelegramDispatcher outbox; private final TerminalTelegramGateway gateway; private final TerminalTraceCollector traces;
  private final TerminalProperties terminal; private final AtomicLong updateIds = new AtomicLong(System.currentTimeMillis() * 1_000L);

  public TerminalConversation(UpdateService updates, TelegramInboxWorker inbox, OutboundTelegramDispatcher outbox, TerminalTelegramGateway gateway, TerminalTraceCollector traces, TerminalProperties terminal, BotProperties bot) {
    this.updates=updates; this.inbox=inbox; this.outbox=outbox; this.gateway=gateway; this.traces=traces; this.terminal=terminal;
    Set<Long> allowed=bot.allowedTelegramUserIds();
    if (!allowed.contains(terminal.userId())) throw new IllegalStateException("food-journal.terminal.user-id must be present in ALLOWED_TELEGRAM_USER_IDS");
  }

  public Result send(String text) throws InterruptedException {
    long updateId=updateIds.incrementAndGet();
    TelegramUser user=new TelegramUser(terminal.userId(), terminal.displayName());
    TelegramUpdate update=new TelegramUpdate(updateId, new TelegramMessage(updateId, new TelegramChat(terminal.userId()), user, text, null, null, null), null);
    updates.enqueue(update);
    inbox.dispatch();
    outbox.dispatch();
    TerminalTelegramGateway.Delivery delivery=gateway.await(updateId, REPLY_TIMEOUT);
    if (delivery==null) throw new IllegalStateException("No terminal reply arrived within " + REPLY_TIMEOUT.toSeconds() + " seconds");
    return new Result(delivery.text(), traces.await());
  }
}
