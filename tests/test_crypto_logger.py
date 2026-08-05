import logging

import bundled_adapter


def test_mautrix_crypto_logger_supports_nonstandard_trace_levels(caplog):
    crypto_log = logging.getLogger("mau.crypto")
    assert not hasattr(crypto_log, "trace")

    with caplog.at_level(logging.DEBUG, logger="mau.crypto"):
        compat_log = bundled_adapter._mautrix_crypto_logger()
        compat_log.trace("encrypted to-device event")
        compat_log.silly("crypto detail")

    assert "encrypted to-device event" in caplog.text
    assert "crypto detail" in caplog.text
