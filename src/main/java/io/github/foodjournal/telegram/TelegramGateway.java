package io.github.foodjournal.telegram;
public interface TelegramGateway { long sendMessage(long chatId, String text); void editMessage(long chatId,long messageId,String text); void pinMessage(long chatId,long messageId); }
