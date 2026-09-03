from app.repositories.food_entry_repo import normalized


def test_normalized_folds_romanian_diacritics_and_case():
    assert normalized("dulceață de ardei iute") == normalized("Dulceata De Ardei Iute")
    assert normalized("dulceata") in normalized("dulceață de ardei iute")


def test_normalized_handles_none_and_empty_text():
    assert normalized(None) == ""
    assert normalized("") == ""
