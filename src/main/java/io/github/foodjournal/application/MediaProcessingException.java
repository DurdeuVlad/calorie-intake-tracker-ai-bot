package io.github.foodjournal.application;

public class MediaProcessingException extends RuntimeException {
 public enum Category { NOT_CONFIGURED, TELEGRAM_DOWNLOAD, INVALID_MEDIA, MODEL_UNAVAILABLE, RATE_LIMITED, PROVIDER_TEMPORARY, PROVIDER_RESPONSE }
 private final Category category;
 public MediaProcessingException(Category category,String message){super(message);this.category=category;}
 public MediaProcessingException(Category category,String message,Throwable cause){super(message,cause);this.category=category;}
 public Category category(){return category;}
}
