package io.github.foodjournal.terminal;

/** Local-only extension that retains the durable outbox source update identifier. */
public interface TerminalDeliveryGateway {
  long sendTerminalMessage(long chatId, String text, Long sourceUpdateId);
}
