#!/usr/bin/env python3
"""
Bot Telegram Hyperliquid - VRAIES LIQUIDATIONS WebSocket
Version finale basée sur la recherche API
"""

import asyncio
import json
import logging
import sys
import urllib.request
import urllib.parse
import time
from datetime import datetime

# Configuration
try:
    from config_railway import Config
except ImportError:
    from config_temp import Config

# Logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.channel_id = Config.TELEGRAM_CHANNEL_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.messages_sent = 0
        self.last_message_time = 0
        self.min_interval = 1
    
    async def send_message(self, text: str):
        """Envoyer un message avec limitation de taux"""
        try:
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

class HyperliquidLiquidationsBot:
    def __init__(self):
        self.telegram_bot = TelegramBot()
        self.running = False
        self.min_liquidation_value = getattr(Config, 'MIN_LIQUIDATION_VALUE', 50000)
        self.liquidations_count = 0
        self.processed_hashes = set()  # Éviter les doublons
        
    async def start(self):
        """Démarrer le bot avec polling des trades"""
        try:
            logger.info("🚀 Démarrage bot LIQUIDATIONS Hyperliquid...")
            
            startup_msg = f"""🚀 **BOT HYPERLIQUID LIQUIDATIONS**

✅ **Vraies liquidations** détectées via API
🎯 **Méthode**: Analyse trades + userFills
💰 **Seuil: ${self.min_liquidation_value:,}+**
🔴 **LONG** = Point rouge  
🟢 **SHORT** = Point vert
📊 **Format: 🔴/🟢 #TOKEN DIRECTION $XXK @$PRIX**

🔍 Surveillance en cours..."""
            
            await self.telegram_bot.send_message(startup_msg)
            
            # Démarrer la surveillance
            self.running = True
            await self.monitor_liquidations()
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            return False
    
    async def get_all_coins(self):
        """Récupérer tous les coins disponibles"""
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "meta"}
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            if result and 'universe' in result:
                coins = [asset['name'] for asset in result['universe'] if 'name' in asset]
                return coins[:50]  # Limiter à 50 coins les plus populaires
            
            return ['BTC', 'ETH', 'SOL', 'AVAX', 'DOGE']
            
        except Exception as e:
            logger.error(f"❌ Erreur coins: {e}")
            return ['BTC', 'ETH', 'SOL', 'AVAX', 'DOGE']
    
    async def monitor_liquidations(self):
        """Surveiller les liquidations en continu"""
        scan_count = 0
        
        while self.running:
            try:
                scan_count += 1
                logger.info(f"🔍 Scan #{scan_count} liquidations...")
                
                # Récupérer les coins à surveiller
                coins = await self.get_all_coins()
                
                # Surveiller par batch
                batch_size = 10
                for i in range(0, len(coins), batch_size):
                    batch = coins[i:i+batch_size]
                    
                    # Traiter chaque coin du batch
                    tasks = []
                    for coin in batch:
                        tasks.append(self.analyze_coin_liquidations(coin))
                    
                    # Exécuter en parallèle
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Traiter les résultats
                    total_liquidations = 0
                    for result in results:
                        if isinstance(result, list):
                            total_liquidations += len(result)
                            for liquidation in result:
                                await self.send_liquidation_alert(liquidation)
                                await asyncio.sleep(0.5)  # Pause entre alertes
                    
                    if total_liquidations > 0:
                        logger.info(f"🚨 {total_liquidations} liquidations trouvées dans ce batch")
                    
                    # Pause entre batches
                    await asyncio.sleep(2)
                
                # Attendre avant le prochain scan
                await asyncio.sleep(30)  # Scan toutes les 30 secondes
                
            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                await asyncio.sleep(60)
    
    async def analyze_coin_liquidations(self, coin):
        """Analyser les liquidations d'un coin spécifique"""
        try:
            # Récupérer les trades récents
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "recentTrades", "coin": coin}
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=8) as response:
                trades = json.loads(response.read().decode('utf-8'))
            
            if not trades:
                return []
            
            liquidations = []
            current_time = time.time() * 1000
            five_minutes_ago = current_time - (5 * 60 * 1000)
            
            for trade in trades:
                try:
                    trade_time = trade.get('time', 0)
                    trade_hash = trade.get('hash', '')
                    
                    # Éviter les doublons
                    if trade_hash in self.processed_hashes:
                        continue
                    
                    # Seulement les trades très récents
                    if trade_time < five_minutes_ago:
                        continue
                    
                    sz = float(trade.get('sz', 0))
                    px = float(trade.get('px', 0))
                    side = trade.get('side', '')
                    users = trade.get('users', [])
                    value_usd = sz * px
                    
                    # Critères stricts pour identifier une liquidation
                    is_liquidation = False
                    
                    # Critère 1: Valeur minimale
                    if value_usd < self.min_liquidation_value:
                        continue
                    
                    # Critère 2: Taille très significative (liquidations = gros volumes)
                    if coin == 'BTC':
                        is_liquidation = sz >= 2.0  # Au moins 2 BTC
                    elif coin == 'ETH':
                        is_liquidation = sz >= 20.0  # Au moins 20 ETH
                    elif coin in ['SOL', 'AVAX', 'MATIC', 'DOT', 'LINK']:
                        is_liquidation = sz >= 1000.0  # Au moins 1000 tokens
                    elif coin in ['DOGE', 'XRP', 'ADA']:
                        is_liquidation = sz >= 50000.0  # Au moins 50K tokens
                    else:
                        is_liquidation = sz >= 5000.0  # Au moins 5K autres tokens
                    
                    # Critère 3: Plusieurs utilisateurs impliqués (signe de liquidation forcée)
                    if len(users) >= 2:
                        is_liquidation = True
                    
                    # Critère 4: Volume exceptionnel par rapport au prix
                    if value_usd >= 100000:  # >100K toujours suspect
                        is_liquidation = True
                    
                    if is_liquidation:
                        liquidation = {
                            'coin': coin,
                            'sz': sz,
                            'px': px,
                            'side': side,
                            'value_usd': value_usd,
                            'time': trade_time,
                            'hash': trade_hash,
                            'users': users
                        }
                        liquidations.append(liquidation)
                        self.processed_hashes.add(trade_hash)
                        
                except Exception as e:
                    continue
            
            return liquidations
            
        except Exception as e:
            logger.error(f"❌ Erreur analyse {coin}: {e}")
            return []
    
    async def send_liquidation_alert(self, liquidation):
        """Envoyer une alerte de liquidation"""
        try:
            self.liquidations_count += 1
            
            coin = liquidation['coin']
            sz = liquidation['sz']
            px = liquidation['px']
            side = liquidation['side']
            value_usd = liquidation['value_usd']
            users_count = len(liquidation.get('users', []))
            
            # Point rouge pour LONG, vert pour SHORT
            if side.lower() in ['sell', 'short', 's']:
                point = "🟢"
                direction = "SHORT"
            else:
                point = "🔴"
                direction = "LONG"
            
            # Formater le montant
            if value_usd >= 1000000:
                amount_str = f"${value_usd/1000000:.1f}M"
            elif value_usd >= 1000:
                amount_str = f"${value_usd/1000:.0f}K"
            else:
                amount_str = f"${value_usd:.0f}"
            
            # Message avec indicateur de confiance
            confidence = "🚨" if users_count >= 2 or value_usd >= 100000 else "⚠️"
            message = f"{confidence} {point} #{coin} {direction} {amount_str} @${px:.4f}"
            
            await self.telegram_bot.send_message(message)
            logger.info(f"🚨 Liquidation #{self.liquidations_count}: {coin} {amount_str} (users: {users_count})")
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi alerte: {e}")
    
    def stop(self):
        """Arrêter le bot"""
        logger.info("🛑 Arrêt du bot liquidations...")
        self.running = False

async def main():
    """Fonction principale"""
    logger.info("🚀 === BOT LIQUIDATIONS HYPERLIQUID FINAL ===")
    
    try:
        Config.validate()
        logger.info("✅ Configuration valide")
        
    except Exception as e:
        logger.error(f"❌ Erreur configuration: {e}")
        return False
    
    # Démarrer le bot
    bot = HyperliquidLiquidationsBot()
    
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
