#!/usr/bin/env python3
"""
Bot Telegram Hyperliquid pour Railway
Version optimisée pour l'hébergement cloud
"""

import asyncio
import json
import logging
import sys
import urllib.request
import urllib.parse
from datetime import datetime
import time
from collections import defaultdict

# Essayer d'importer la configuration Railway, sinon utiliser la locale
try:
    from config_railway import Config
except ImportError:
    from config_temp import Config

# Configuration du logging pour Railway
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]  # Railway capture stdout
)

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.channel_id = Config.TELEGRAM_CHANNEL_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.messages_sent = 0
        self.last_message_time = 0
        self.min_interval = 3  # Minimum 3 secondes entre les messages
    
    async def send_message(self, text: str):
        """Envoyer un message avec limitation de taux"""
        try:
            # Respecter la limitation de taux
            current_time = time.time()
            time_since_last = current_time - self.last_message_time
            
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                await asyncio.sleep(wait_time)
            
            url = f"{self.base_url}/sendMessage"
            
            data = {
                'chat_id': self.channel_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            
            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            if result.get('ok'):
                self.messages_sent += 1
                self.last_message_time = time.time()
                logger.info(f"✅ Message #{self.messages_sent} envoyé")
                return True
            else:
                logger.error(f"❌ Erreur Telegram: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur envoi: {e}")
            return False

class HyperliquidBot:
    def __init__(self):
        self.telegram_bot = TelegramBot()
        self.running = False
        self.min_liquidation_value = getattr(Config, 'MIN_LIQUIDATION_VALUE', 50000)
        
    async def start(self):
        """Démarrer le bot Railway"""
        try:
            logger.info("🚀 Démarrage du bot Hyperliquid sur Railway...")
            
            # Message de démarrage
            startup_msg = f"""🚀 **BOT HYPERLIQUID RAILWAY**

✅ Hébergé sur Railway (gratuit)
📊 **43 cryptos** surveillées
⚡ **Alertes INSTANTANÉES**
💰 **Seuil: ${self.min_liquidation_value:,}**
📝 **Format: 🔴/🟢 #TOKEN DIRECTION $MONTANT @PRIX**

🌐 Démarrage surveillance..."""
            
            await self.telegram_bot.send_message(startup_msg)
            
            # Démarrer la surveillance
            self.running = True
            await self.monitor_liquidations()
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            return False
    
    async def monitor_liquidations(self):
        """Surveiller les liquidations en continu"""
        check_count = 0
        
        # Liste complète des cryptos
        coins_to_check = [
            # Top cryptos
            'BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'DOT', 'LINK', 'UNI',
            # Nouvelles additions
            'ASTER', 'ADA', 'XRP', 'DOGE', 'SHIB', 'LTC', 'BCH', 'ETC',
            # DeFi tokens
            'AAVE', 'COMP', 'MKR', 'SNX', 'CRV', 'SUSHI', 'YFI', '1INCH',
            # Layer 1s
            'ATOM', 'NEAR', 'FTM', 'ALGO', 'EGLD', 'FLOW', 'ICP', 'TEZOS',
            # Gaming/NFT
            'AXS', 'SAND', 'MANA', 'ENJ', 'GALA', 'IMX', 'THETA', 'CHZ',
            # Autres populaires
            'FIL', 'VET', 'TRX', 'EOS', 'XLM', 'HBAR', 'IOTA', 'NEO',
            # Meme coins
            'PEPE', 'FLOKI', 'BONK', 'WIF', 'BOME'
        ]
        
        while self.running:
            try:
                check_count += 1
                logger.info(f"🔍 Scan #{check_count} des liquidations...")
                
                # Surveiller par batch pour Railway
                batch_size = 6  # Plus petit batch pour Railway
                start_idx = (check_count - 1) * batch_size % len(coins_to_check)
                end_idx = min(start_idx + batch_size, len(coins_to_check))
                current_batch = coins_to_check[start_idx:end_idx]
                
                logger.info(f"📊 Batch Railway: {', '.join(current_batch)}")
                
                for coin in current_batch:
                    try:
                        trades = await self.get_recent_trades(coin)
                        if trades:
                            liquidations = self.identify_liquidations(trades, coin)
                            
                            # Filtrer et envoyer les grosses liquidations
                            for liq in liquidations:
                                try:
                                    sz = float(liq.get('sz', 0))
                                    px = float(liq.get('px', 0))
                                    value = sz * px
                                    
                                    if value >= self.min_liquidation_value:
                                        await self.send_liquidation(liq)
                                        
                                except Exception as e:
                                    logger.error(f"❌ Erreur traitement liquidation: {e}")
                        
                        # Pause entre coins pour Railway
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"❌ Erreur {coin}: {e}")
                        continue
                
                # Attendre avant le prochain scan
                await asyncio.sleep(45)  # Plus long pour Railway
                
            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                await asyncio.sleep(120)  # Pause plus longue en cas d'erreur
    
    async def send_liquidation(self, liq):
        """Envoyer une liquidation"""
        try:
            coin = liq.get('coin', 'Unknown')
            sz = float(liq.get('sz', 0))
            px = float(liq.get('px', 0))
            side = liq.get('side', '').upper()
            value_usd = sz * px
            
            # Point rouge ou vert selon la direction
            if side.lower() in ['sell', 'short']:
                point = "🔴"
                direction = "SHORT"
            else:
                point = "🟢"
                direction = "LONG"
            
            # Format simple
            message = f"{point} #{coin} {direction} ${value_usd:,.0f} @${px:.2f}"
            
            await self.telegram_bot.send_message(message)
            logger.info(f"🚨 Liquidation envoyée: {coin} ${value_usd:,.0f}")
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi liquidation: {e}")
    
    async def get_recent_trades(self, coin):
        """Récupérer les trades récents"""
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {
                "type": "recentTrades",
                "coin": coin
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur API {coin}: {e}")
            return None
    
    def identify_liquidations(self, trades, coin):
        """Identifier les liquidations"""
        liquidations = []
        
        if not trades or not isinstance(trades, list):
            return liquidations
        
        # Analyser les trades récents
        current_time = datetime.now().timestamp() * 1000
        one_hour_ago = current_time - (60 * 60 * 1000)
        
        for trade in trades:
            try:
                trade_time = trade.get('time', 0)
                
                if trade_time < one_hour_ago:
                    continue
                
                sz = float(trade.get('sz', 0))
                px = float(trade.get('px', 0))
                side = trade.get('side', '')
                value_usd = sz * px
                
                # Seuils pour identifier les liquidations
                if coin in ['BTC', 'ETH']:
                    is_significant = sz > 0.1 and value_usd > 5000
                elif coin in ['SOL', 'AVAX', 'ADA', 'DOT', 'LINK', 'UNI', 'ATOM', 'NEAR', 'FTM']:
                    is_significant = sz > 5.0 and value_usd > 1000
                elif coin in ['MATIC', 'XRP', 'LTC', 'BCH', 'AAVE', 'COMP', 'MKR', 'ALGO', 'FIL', 'VET']:
                    is_significant = sz > 10.0 and value_usd > 800
                elif coin in ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'BOME']:
                    is_significant = sz > 1000.0 and value_usd > 500
                else:
                    is_significant = sz > 20.0 and value_usd > 500
                
                if is_significant:
                    liquidation = {
                        'coin': coin,
                        'sz': str(sz),
                        'px': str(px),
                        'side': side,
                        'time': trade_time
                    }
                    liquidations.append(liquidation)
                    
            except Exception as e:
                continue
        
        return liquidations
    
    def stop(self):
        """Arrêter le bot"""
        logger.info("🛑 Arrêt du bot Railway...")
        self.running = False

async def main():
    """Fonction principale pour Railway"""
    logger.info("🚀 === BOT HYPERLIQUID RAILWAY ===")
    
    try:
        # Valider la configuration
        Config.validate()
        logger.info("✅ Configuration Railway valide")
        
    except Exception as e:
        logger.error(f"❌ Erreur configuration: {e}")
        return False
    
    # Démarrer le bot
    bot = HyperliquidBot()
    
    try:
        await bot.start()
        return True
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot interrompu")
        bot.stop()
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        bot.stop()
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}")
        sys.exit(1)
