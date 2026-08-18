package io.github.foodjournal.terminal;

import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.messaging.InboundMessage;
import io.github.foodjournal.messaging.MessagingDispatcher;
import io.github.foodjournal.messaging.MessagingIngressService;
import io.github.foodjournal.messaging.MessagingInboxWorker;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** Sends a synthetic text update through the normal durable inbox and outbox path, using the "terminal" provider. */
@Component @Profile("terminal")
public class TerminalConversation {
  public record Result(String reply, TerminalTraceCollector.Trace trace) {}
  private static final Duration REPLY_TIMEOUT = Duration.ofSeconds(45);
  private final MessagingIngressService ingress; private final MessagingInboxWorker inbox; private final MessagingDispatcher outbox; private final TerminalFrontend frontend; private final TerminalTraceCollector traces;
  private final TerminalProperties terminal; private final AtomicLong eventIds = new AtomicLong(System.currentTimeMillis() * 1_000L);

  public TerminalConversation(MessagingIngressService ingress, MessagingInboxWorker inbox, MessagingDispatcher outbox, TerminalFrontend frontend, TerminalTraceCollector traces, TerminalProperties terminal, BotProperties bot) {
    this.ingress=ingress; this.inbox=inbox; this.outbox=outbox; this.frontend=frontend; this.traces=traces; this.terminal=terminal;
    Set<Long> allowed=bot.allowedTelegramUserIds();
    if (!allowed.contains(terminal.userId())) throw new IllegalStateException("food-journal.terminal.user-id must be present in ALLOWED_TELEGRAM_USER_IDS");
  }

  public Result send(String text) throws InterruptedException {
    frontend.reset();
    String userId = String.valueOf(terminal.userId());
    String eventId = String.valueOf(eventIds.incrementAndGet());
    ingress.accept(new InboundMessage("terminal", eventId, userId, userId, terminal.displayName(), null, text, null, List.of()));
    Instant deadline = Instant.now().plus(REPLY_TIMEOUT); String reply = null;
    while (reply == null && Instant.now().isBefore(deadline)) { inbox.dispatch(); outbox.dispatch(); reply = frontend.awaitReply(Duration.ofMillis(100)); }
    if (reply == null) throw new IllegalStateException("No terminal reply arrived within " + REPLY_TIMEOUT.toSeconds() + " seconds");
    return new Result(reply, traces.await());
  }
}
