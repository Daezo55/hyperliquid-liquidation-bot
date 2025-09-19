import os

class Config:
    # Configuration Telegram - Variables d'environnement Railway
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8472790618:AAGCvy_wnIAHqqMqLnWdHiq9rNfn4PYICJk')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '-1003023975770')
    
    # Configuration Hyperliquid
    HYPERLIQUID_WS_URL = os.getenv('HYPERLIQUID_WS_URL', 'wss://api.hyperliquid.xyz/ws')
    
    # Configuration générale
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    RECONNECT_DELAY = int(os.getenv('RECONNECT_DELAY', 5))
    MIN_LIQUIDATION_VALUE = int(os.getenv('MIN_LIQUIDATION_VALUE', 50000))
    
    @classmethod
    def validate(cls):
        """Valide que toutes les configurations requises sont présentes"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN est requis")
        if not cls.TELEGRAM_CHANNEL_ID:
            raise ValueError("TELEGRAM_CHANNEL_ID est requis")
        return True
