package io.github.foodjournal.messaging;
import java.util.function.Supplier;
public final class MessagingExecutionContext { private static final ThreadLocal<Boolean> ACTIVE=new ThreadLocal<>(); private MessagingExecutionContext(){} public static <T>T run(Supplier<T> work){ACTIVE.set(true);try{return work.get();}finally{ACTIVE.remove();}} public static boolean active(){return Boolean.TRUE.equals(ACTIVE.get());} }
