#!/usr/bin/env python3
"""
Bot Telegram Hyperliquid - FUTURES/PERP LIQUIDATIONS
Version automatique - Tous les tokens, liquidations futures uniquement
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

# Configuration
try:
    from config_railway import Config
except ImportError:
    from config_temp import Config

# Logging pour Railway
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
        self.min_interval = 2  # 2 secondes entre messages
    
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

class HyperliquidFuturesBot:
    def __init__(self):
        self.telegram_bot = TelegramBot()
        self.running = False
        self.min_liquidation_value = getattr(Config, 'MIN_LIQUIDATION_VALUE', 50000)
        self.all_tokens = set()  # Cache des tokens
        self.last_token_update = 0
        
    async def start(self):
        """Démarrer le bot futures"""
        try:
            logger.info("🚀 Démarrage du bot Hyperliquid FUTURES/PERP...")
            
            # Message de démarrage
            startup_msg = f"""🚀 **BOT HYPERLIQUID FUTURES/PERP**

✅ **LIQUIDATIONS FUTURES** uniquement
🔄 **TOUS LES TOKENS** automatiquement
⚡ **Détection automatique** nouveaux tokens
💰 **Seuil minimum: ${self.min_liquidation_value:,}**
📝 **Format: 🔴/🟢 #TOKEN DIRECTION $MONTANT @PRIX**

🌐 Connexion API Hyperliquid futures..."""
            
            await self.telegram_bot.send_message(startup_msg)
            
            # Démarrer la surveillance
            self.running = True
            await self.monitor_all_futures_liquidations()
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            return False
    
    async def get_all_tradable_assets(self):
        """Récupérer TOUS les assets tradables (futures/perp)"""
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "meta"}
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            if result and 'universe' in result:
                # Extraire tous les symbols des futures/perp
                tokens = []
                for asset in result['universe']:
                    if 'name' in asset:
                        token = asset['name']
                        tokens.append(token)
                
                logger.info(f"📊 {len(tokens)} tokens futures/perp trouvés")
                return tokens
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération assets: {e}")
            return []
    
    async def get_liquidations_data(self):
        """Récupérer les données de liquidations directement"""
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "clearinghouseState", "user": "0x0000000000000000000000000000000000000000"}
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur liquidations: {e}")
            return None
    
    async def get_recent_trades_all_tokens(self):
        """Récupérer les trades récents pour TOUS les tokens"""
        try:
            # Mettre à jour la liste des tokens toutes les heures
            current_time = time.time()
            if current_time - self.last_token_update > 3600:  # 1 heure
                new_tokens = await self.get_all_tradable_assets()
                if new_tokens:
                    old_count = len(self.all_tokens)
                    self.all_tokens.update(new_tokens)
                    new_count = len(self.all_tokens)
                    if new_count > old_count:
                        logger.info(f"🆕 {new_count - old_count} nouveaux tokens détectés")
                    self.last_token_update = current_time
            
            # Si pas de tokens en cache, récupérer
            if not self.all_tokens:
                self.all_tokens.update(await self.get_all_tradable_assets())
            
            return list(self.all_tokens)
            
        except Exception as e:
            logger.error(f"❌ Erreur tokens: {e}")
            return ['BTC', 'ETH', 'SOL']  # Fallback
    
    async def get_futures_liquidations(self, token):
        """Récupérer les liquidations futures pour un token"""
        try:
            # Utiliser l'API des trades récents mais filtrer pour les liquidations
            url = "https://api.hyperliquid.xyz/info"
            payload = {
                "type": "recentTrades",
                "coin": token
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            # Filtrer pour les liquidations (trades avec volumes élevés et prix suspects)
            liquidations = []
            if result and isinstance(result, list):
                current_time = datetime.now().timestamp() * 1000
                ten_minutes_ago = current_time - (10 * 60 * 1000)  # 10 minutes
                
                for trade in result:
                    try:
                        trade_time = trade.get('time', 0)
                        if trade_time < ten_minutes_ago:
                            continue
                        
                        sz = float(trade.get('sz', 0))
                        px = float(trade.get('px', 0))
                        side = trade.get('side', '')
                        
                        # Critères pour identifier une liquidation futures
                        value_usd = sz * px
                        
                        # Seuils dynamiques selon le token
                        is_liquidation = False
                        
                        if token in ['BTC', 'ETH']:
                            # Pour BTC/ETH, liquidations = gros volumes
                            is_liquidation = sz > 0.5 and value_usd > 10000
                        elif value_usd > 5000:
                            # Pour autres tokens, seuil plus bas mais volume significatif
                            is_liquidation = True
                        
                        if is_liquidation and value_usd >= self.min_liquidation_value:
                            liquidation = {
                                'coin': token,
                                'sz': str(sz),
                                'px': str(px),
                                'side': side,
                                'time': trade_time,
                                'value_usd': value_usd
                            }
                            liquidations.append(liquidation)
                            
                    except Exception as e:
                        continue
            
            return liquidations
            
        except Exception as e:
            logger.error(f"❌ Erreur liquidations {token}: {e}")
            return []
    
    async def monitor_all_futures_liquidations(self):
        """Surveiller les liquidations futures de TOUS les tokens"""
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                logger.info(f"🔍 Scan #{check_count} liquidations futures...")
                
                # Récupérer tous les tokens
                all_tokens = await self.get_recent_trades_all_tokens()
                logger.info(f"📊 Surveillance de {len(all_tokens)} tokens futures")
                
                # Surveiller par batch pour éviter la surcharge
                batch_size = 10  # 10 tokens par batch
                
                for i in range(0, len(all_tokens), batch_size):
                    batch = all_tokens[i:i+batch_size]
                    logger.info(f"📊 Batch: {', '.join(batch[:5])}{'...' if len(batch) > 5 else ''}")
                    
                    # Traiter chaque token du batch
                    tasks = []
                    for token in batch:
                        tasks.append(self.process_token_liquidations(token))
                    
                    # Exécuter en parallèle
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Pause entre les batches
                    await asyncio.sleep(2)
                
                # Attendre avant le prochain scan complet
                await asyncio.sleep(30)  # Scan toutes les 30 secondes
                
            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                await asyncio.sleep(60)
    
    async def process_token_liquidations(self, token):
        """Traiter les liquidations d'un token"""
        try:
            liquidations = await self.get_futures_liquidations(token)
            
            for liquidation in liquidations:
                await self.send_liquidation_alert(liquidation)
                await asyncio.sleep(0.5)  # Pause entre les alertes
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement {token}: {e}")
    
    async def send_liquidation_alert(self, liquidation):
        """Envoyer une alerte de liquidation"""
        try:
            coin = liquidation.get('coin', 'Unknown')
            sz = float(liquidation.get('sz', 0))
            px = float(liquidation.get('px', 0))
            side = liquidation.get('side', '').upper()
            value_usd = liquidation.get('value_usd', sz * px)
            
            # Point rouge pour LONG, vert pour SHORT (inversé comme demandé)
            if side.lower() in ['sell', 'short']:
                point = "🟢"
                direction = "SHORT"
            else:
                point = "🔴"
                direction = "LONG"
            
            # Formater le montant avec K
            if value_usd >= 1000000:
                amount_str = f"${value_usd/1000000:.1f}M"
            elif value_usd >= 1000:
                amount_str = f"${value_usd/1000:.0f}K"
            else:
                amount_str = f"${value_usd:.0f}"
            
            # Message simple et direct avec nouveau format
            message = f"{point} #{coin} {direction} {amount_str} @${px:.4f}"
            
            await self.telegram_bot.send_message(message)
            logger.info(f"🚨 Liquidation futures envoyée: {coin} {amount_str}")
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi liquidation: {e}")
    
    def stop(self):
        """Arrêter le bot"""
        logger.info("🛑 Arrêt du bot futures...")
        self.running = False

async def main():
    """Fonction principale"""
    logger.info("🚀 === BOT HYPERLIQUID FUTURES/PERP ===")
    
    try:
        Config.validate()
        logger.info("✅ Configuration valide")
        
    except Exception as e:
        logger.error(f"❌ Erreur configuration: {e}")
        return False
    
    # Démarrer le bot
    bot = HyperliquidFuturesBot()
    
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
