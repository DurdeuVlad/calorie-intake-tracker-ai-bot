package io.github.foodjournal.terminal;

import io.github.foodjournal.application.TransientVoicePayload;
import io.github.foodjournal.messaging.Attachment;
import io.github.foodjournal.messaging.MessagingFrontend;
import java.time.Duration;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** Local stand-in transport for the "terminal" provider; captures replies in-process instead of calling a real API. Terminal usage is single-threaded, so no correlation id is needed between a send and its reply. */
@Component
@Profile("terminal")
public class TerminalFrontend implements MessagingFrontend {
  private final BlockingQueue<String> deliveries = new LinkedBlockingQueue<>();

  @Override public String provider() { return "terminal"; }
  @Override public boolean enabled() { return true; }
  @Override public int messageLimit() { return 4096; }
  @Override public String send(String conversationId, String text) { deliveries.add(text); return "0"; }
  @Override public void edit(String conversationId, String messageId, String text) { deliveries.add(text); }
  @Override public TransientVoicePayload download(Attachment attachment) { throw new UnsupportedOperationException("Terminal mode does not support media attachments"); }

  public String awaitReply(Duration timeout) throws InterruptedException {
    return deliveries.poll(timeout.toNanos(), TimeUnit.NANOSECONDS);
  }

  public void reset() { deliveries.clear(); }
}
