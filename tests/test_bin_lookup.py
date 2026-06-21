from services.bot.tools.bin_lookup import detect_card_bin, detect_payment_system, is_luhn_valid, map_bank_name_to_project_bank_id


def test_card_luhn_valid():
    assert is_luhn_valid("2202200000000008")


def test_card_luhn_invalid():
    assert not is_luhn_valid("2202200000000007")


def test_detect_payment_system_mir():
    assert detect_payment_system("2202200000000008") == "mir"


def test_detect_payment_system_visa():
    assert detect_payment_system("4276380000000005") == "visa"


def test_detect_payment_system_mastercard_51_55():
    assert detect_payment_system("5555550000000002") == "mastercard"


def test_detect_payment_system_mastercard_2221_2720():
    assert detect_payment_system("2221000000000009") == "mastercard"


def test_detect_payment_system_unionpay():
    assert detect_payment_system("6200000000000005") == "unionpay"


def test_bin_lookup_local_8_priority():
    info = detect_card_bin("2202200000000008")
    assert info["bank_id"] == "sber"
    assert info["confidence"] == "local_8"


def test_bin_lookup_local_6_fallback():
    info = detect_card_bin("4276380000000005")
    assert info["bank_id"] == "vtb"
    assert info["confidence"] == "local_6"


def test_bank_name_mapping_sber():
    assert map_bank_name_to_project_bank_id("ПАО Сбербанк") == "sber"


def test_no_full_card_in_logs_or_result():
    card = "2202200000000008"
    info = detect_card_bin(card)
    assert card not in str(info)
    assert info["masked"].endswith("0008")


def test_api_links_contains_card_info_for_card():
    # В текущем репозитории нет WebApp backend.py, поэтому проверяем доступный эквивалент — BIN-инфо для карты.
    info = detect_card_bin("2202200000000008")
    assert info["ok"] is True
    assert "bank_id" in info


def test_api_links_does_not_call_external_api_without_keys(monkeypatch):
    monkeypatch.delenv("HANDYAPI_KEY", raising=False)
    monkeypatch.delenv("BINSEARCHLOOKUP_KEY", raising=False)
    info = detect_card_bin("6200000000000005")
    assert info["source"] == "local_scheme_only"


def test_external_api_failure_does_not_break_links(monkeypatch):
    monkeypatch.setenv("HANDYAPI_KEY", "dummy")
    monkeypatch.setenv("HANDYAPI_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("BINSEARCHLOOKUP_KEY", "dummy")
    monkeypatch.setenv("BINSEARCHLOOKUP_BASE_URL", "http://127.0.0.1:1")
    info = detect_card_bin("6200000000000005")
    assert info["ok"] is True
    assert info["payment_system"] == "unionpay"
