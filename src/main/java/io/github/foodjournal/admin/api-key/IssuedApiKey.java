package io.github.foodjournal.admin.api_key;

/** Plaintext is returned once to the authenticated dashboard caller and is never persisted. */
public record IssuedApiKey(long id, String name, String prefix, String plaintext) {}
