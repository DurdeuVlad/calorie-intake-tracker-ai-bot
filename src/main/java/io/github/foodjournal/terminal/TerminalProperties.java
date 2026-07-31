package io.github.foodjournal.terminal;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.ConstructorBinding;

@ConfigurationProperties("food-journal.terminal")
public record TerminalProperties(long userId, String displayName, String evalFile, String reportFile, int evalRepeats, String evalScenario, String evalBaselineFile, boolean evalFullReport) {
  @ConstructorBinding public TerminalProperties {
    if (userId <= 0) userId = 1L;
    if (displayName == null || displayName.isBlank()) displayName = "Local developer";
    evalFile = blankToNull(evalFile);
    reportFile = blankToNull(reportFile);
    if (evalRepeats <= 0) evalRepeats = 3;
    evalScenario = blankToNull(evalScenario);
    evalBaselineFile = blankToNull(evalBaselineFile);
  }
  public TerminalProperties(long userId, String displayName, String evalFile, String reportFile) { this(userId, displayName, evalFile, reportFile, 3, null, null, true); }
  private static String blankToNull(String value) { return value == null || value.isBlank() ? null : value; }
}
