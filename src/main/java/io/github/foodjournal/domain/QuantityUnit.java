package io.github.foodjournal.domain;

import java.util.Locale;

public enum QuantityUnit {
  G("g"), ML("ml"), PORTION("portion"), UNSPECIFIED("unspecified");

  private final String databaseValue;
  QuantityUnit(String databaseValue){this.databaseValue=databaseValue;}
  public String databaseValue(){return databaseValue;}
  public static QuantityUnit fromDatabaseValue(String value){
    if(value==null||value.isBlank())return UNSPECIFIED;
    return switch(value.toLowerCase(Locale.ROOT)){
      case "g" -> G; case "ml" -> ML; case "portion" -> PORTION; case "unspecified" -> UNSPECIFIED;
      default -> throw new IllegalArgumentException("Unsupported quantity unit: "+value);
    };
  }
}
