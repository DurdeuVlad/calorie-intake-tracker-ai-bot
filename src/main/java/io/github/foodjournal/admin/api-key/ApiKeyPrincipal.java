package io.github.foodjournal.admin.api_key;

import java.util.Set;
public record ApiKeyPrincipal(long id, String name, Set<ApiKeyScope> scopes) {}
