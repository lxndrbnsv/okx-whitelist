import pyotp

from config import Config as cfg


class OTP:
    def __init__(self) -> None:
        self.otp = pyotp.TOTP(cfg.OKX_2FA, interval=30).now()
