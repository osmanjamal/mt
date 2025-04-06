from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceAPIException
from binance.enums import *
import config
import json
import datetime
import math
import logging
import time

# إعداد التسجيل لتتبع الأخطاء والعمليات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("binance_api.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("BinanceTrader")

class BinanceTrader:
    """
    فئة للتعامل مع منصة بايننس من خلال API ومحاكاة وظائف MT5
    """
    def __init__(self):
        """
        تهيئة الاتصال ببايننس باستخدام مفاتيح API
        """
        try:
            self.client = Client(
                config.binance_api_key, 
                config.binance_api_secret, 
                testnet=config.binance_testnet
            )
            
            # تعيين الخيارات الأساسية من ملف الإعدادات
            self.account_type = getattr(config, 'account_type', 'futures')  # الافتراضي هو العقود المستقبلية
            self.leverage = getattr(config, 'leverage', 10)  # الافتراضي هو 10x
            
            # جلب معلومات السوق وحفظها للاستخدام اللاحق
            self._update_exchange_info()
            
            logger.info("تم الاتصال بمنصة بايننس بنجاح")
        except Exception as e:
            logger.error(f"خطأ في الاتصال بمنصة بايننس: {e}")
            self.client = None
    
    def _update_exchange_info(self):
        """
        تحديث معلومات التداول من بايننس وحفظها محلياً
        """
        try:
            if self.account_type == 'futures':
                self.exchange_info = self.client.futures_exchange_info()
                self.symbols_info = {item['symbol']: item for item in self.exchange_info['symbols']}
            else:  # spot
                self.exchange_info = self.client.get_exchange_info()
                self.symbols_info = {item['symbol']: item for item in self.exchange_info['symbols']}
            
            logger.info("تم تحديث معلومات التداول من بايننس")
        except Exception as e:
            logger.error(f"خطأ في تحديث معلومات التداول: {e}")
    
    def _get_quantity_precision(self, symbol):
        """
        استرجاع دقة الكمية المطلوبة لرمز معين
        """
        try:
            if symbol in self.symbols_info:
                symbol_info = self.symbols_info[symbol]
                
                if self.account_type == 'futures':
                    for filter_item in symbol_info['filters']:
                        if filter_item['filterType'] == 'LOT_SIZE':
                            step_size = float(filter_item['stepSize'])
                            precision = int(round(-math.log10(step_size)))
                            return precision
                else:  # spot
                    for filter_item in symbol_info['filters']:
                        if filter_item['filterType'] == 'LOT_SIZE':
                            step_size = float(filter_item['stepSize'])
                            precision = int(round(-math.log10(step_size)))
                            return precision
            
            # الافتراضي إذا لم نجد معلومات
            return 5
        except Exception as e:
            logger.error(f"خطأ في استرجاع دقة الكمية: {e}")
            return 5  # قيمة افتراضية آمنة
    
    def _format_quantity(self, symbol, quantity):
        """
        تنسيق الكمية حسب دقة الرمز
        """
        precision = self._get_quantity_precision(symbol)
        formatted_qty = f"{{:.{precision}f}}".format(float(quantity))
        return formatted_qty
    
    def _get_price_precision(self, symbol):
        """
        استرجاع دقة السعر المطلوبة لرمز معين
        """
        try:
            if symbol in self.symbols_info:
                symbol_info = self.symbols_info[symbol]
                
                if self.account_type == 'futures':
                    for filter_item in symbol_info['filters']:
                        if filter_item['filterType'] == 'PRICE_FILTER':
                            tick_size = float(filter_item['tickSize'])
                            precision = int(round(-math.log10(tick_size)))
                            return precision
                else:  # spot
                    for filter_item in symbol_info['filters']:
                        if filter_item['filterType'] == 'PRICE_FILTER':
                            tick_size = float(filter_item['tickSize'])
                            precision = int(round(-math.log10(tick_size)))
                            return precision
            
            # الافتراضي إذا لم نجد معلومات
            return 2
        except Exception as e:
            logger.error(f"خطأ في استرجاع دقة السعر: {e}")
            return 2  # قيمة افتراضية آمنة
    
    def _format_price(self, symbol, price):
        """
        تنسيق السعر حسب دقة الرمز
        """
        precision = self._get_price_precision(symbol)
        formatted_price = f"{{:.{precision}f}}".format(float(price))
        return formatted_price
    
    def _wait_for_order_completion(self, symbol, order_id, timeout=60):
        """
        انتظار اكتمال الطلب
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if self.account_type == 'futures':
                    order = self.client.futures_get_order(symbol=symbol, orderId=order_id)
                else:
                    order = self.client.get_order(symbol=symbol, orderId=order_id)
                
                if order['status'] == 'FILLED':
                    return order
                elif order['status'] in ['REJECTED', 'EXPIRED', 'CANCELED']:
                    logger.warning(f"الطلب {order_id} انتهى بحالة {order['status']}")
                    return order
                
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"خطأ في التحقق من حالة الطلب: {e}")
                return None
        
        logger.warning(f"انتهت مهلة انتظار اكتمال الطلب {order_id}")
        return None
    
    def initialize(self):
        """
        التهيئة المبدئية للاتصال - يحاكي initialize() في MT5
        """
        if self.client:
            try:
                # اختبار الاتصال من خلال جلب وقت الخادم
                server_time = self.client.get_server_time()
                
                # تحديث معلومات التداول
                self._update_exchange_info()
                
                # التهيئة ناجحة
                return True
            except Exception as e:
                logger.error(f"فشل التهيئة: {e}")
                return False
        return False
    
    def account_info(self):
        """
        استرجاع معلومات الحساب المشابهة لـ account_info في MT5
        """
        try:
            if self.account_type == 'futures':
                account = self.client.futures_account()
                
                # تحويل البيانات لتشبه مخرجات MT5
                info = {
                    'login': account['totalWalletBalance'],  # استخدام الرصيد كرقم تعريفي
                    'balance': float(account['totalWalletBalance']),
                    'equity': float(account['totalMarginBalance']),
                    'margin': float(account['totalMaintMargin']),
                    'margin_level': float(account['totalMarginBalance']) / float(account['totalMaintMargin']) * 100 if float(account['totalMaintMargin']) > 0 else 0,
                    'margin_free': float(account['availableBalance'])
                }
                
                # تحويل إلى صيغة _asdict()
                class AccountInfo:
                    def __init__(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)
                    
                    def _asdict(self):
                        return {key: value for key, value in self.__dict__.items()}
                
                return AccountInfo(**info)
            else:
                account = self.client.get_account()
                
                # حساب القيم المهمة
                total_balance = sum([float(balance['free']) + float(balance['locked']) for balance in account['balances'] if float(balance['free']) + float(balance['locked']) > 0])
                
                # تحويل البيانات لتشبه مخرجات MT5
                info = {
                    'login': total_balance,  # استخدام الرصيد كرقم تعريفي
                    'balance': total_balance,
                    'equity': total_balance,
                    'margin': 0,  # لا ينطبق على التداول الفوري
                    'margin_level': 0,  # لا ينطبق على التداول الفوري
                    'margin_free': total_balance
                }
                
                # تحويل إلى صيغة _asdict()
                class AccountInfo:
                    def __init__(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)
                    
                    def _asdict(self):
                        return {key: value for key, value in self.__dict__.items()}
                
                return AccountInfo(**info)
        except Exception as e:
            logger.error(f"خطأ في استرجاع معلومات الحساب: {e}")
            
            # إرجاع بيانات افتراضية في حالة الخطأ
            info = {
                'login': 0,
                'balance': 0,
                'equity': 0,
                'margin': 0,
                'margin_level': 0,
                'margin_free': 0
            }
            
            class AccountInfo:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                
                def _asdict(self):
                    return {key: value for key, value in self.__dict__.items()}
            
            return AccountInfo(**info)
    
    def symbol_info(self, symbol):
        """
        استرجاع معلومات رمز التداول
        """
        try:
            # تحديث المعلومات أولاً
            self._update_exchange_info()
            
            if symbol in self.symbols_info:
                return self.symbols_info[symbol]
            else:
                logger.warning(f"الرمز {symbol} غير موجود")
                return None
        except Exception as e:
            logger.error(f"خطأ في استرجاع معلومات الرمز: {e}")
            return None
    
    def set_leverage(self, symbol, leverage=None):
        """
        تعيين الرافعة المالية للرمز (للعقود المستقبلية فقط)
        """
        if self.account_type != 'futures':
            logger.warning("تعيين الرافعة المالية متاح فقط في حسابات العقود المستقبلية")
            return None
        
        try:
            # استخدام الرافعة من الإعدادات إن لم يتم تحديدها
            leverage_to_set = leverage if leverage is not None else self.leverage
            
            result = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage_to_set
            )
            
            logger.info(f"تم تعيين الرافعة المالية للرمز {symbol} إلى {leverage_to_set}x")
            return result
        except BinanceAPIException as e:
            logger.error(f"خطأ في تعيين الرافعة المالية: {e}")
            return None
    
    def positions_get(self, symbol=None):
        """
        استرجاع المراكز المفتوحة - يحاكي positions_get في MT5
        """
        try:
            positions = []
            
            if self.account_type == 'futures':
                # للعقود المستقبلية
                account = self.client.futures_account()
                positions_info = account['positions']
                
                for pos in positions_info:
                    # فقط المراكز المفتوحة (ذات كمية غير صفرية)
                    pos_amt = float(pos['positionAmt'])
                    if pos_amt != 0:
                        if symbol is None or pos['symbol'] == symbol:
                            # تحويل البيانات إلى صيغة مشابهة لـ MT5
                            position_data = {
                                'symbol': pos['symbol'],
                                'volume': abs(pos_amt),
                                'price_open': float(pos['entryPrice']),
                                'price_current': float(pos['markPrice']),
                                'profit': float(pos['unrealizedProfit']),
                                'time': int(time.time()),  # الوقت الحالي كتقريب
                                'comment': 'SELL' if pos_amt < 0 else 'BUY',
                                'identifier': pos['symbol']  # استخدام الرمز كمعرف للمركز
                            }
                            
                            # تحويل إلى صيغة _asdict() المشابهة لـ MT5
                            class Position:
                                def __init__(self, **kwargs):
                                    for key, value in kwargs.items():
                                        setattr(self, key, value)
                                
                                def _asdict(self):
                                    return {key: value for key, value in self.__dict__.items()}
                            
                            positions.append(Position(**position_data))
            else:
                # للتداول الفوري
                balances = self.client.get_account()['balances']
                
                for balance in balances:
                    free_amount = float(balance['free'])
                    locked_amount = float(balance['locked'])
                    
                    # فقط العملات التي لها رصيد
                    if free_amount > 0 or locked_amount > 0:
                        # في التداول الفوري، نعتبر أي رصيد موجب كمركز "شراء"
                        asset = balance['asset']
                        
                        # التحقق ما إذا كانت العملة مرتبطة بالرمز المطلوب
                        if symbol is None or asset in symbol:
                            # محاولة الحصول على سعر العملة
                            current_price = 0
                            try:
                                if asset != 'USDT':  # لأن USDT هي العملة الأساسية
                                    ticker = self.client.get_symbol_ticker(symbol=f"{asset}USDT")
                                    current_price = float(ticker['price'])
                            except:
                                # إذا لم يمكن الحصول على السعر، نستخدم 1 كافتراضي
                                current_price = 1
                            
                            # تحويل البيانات إلى صيغة مشابهة لـ MT5
                            position_data = {
                                'symbol': asset,
                                'volume': free_amount + locked_amount,
                                'price_open': 0,  # لا يمكن معرفة سعر الشراء الأصلي
                                'price_current': current_price,
                                'profit': 0,  # لا يمكن حساب الربح بدون سعر الشراء
                                'time': int(time.time()),  # الوقت الحالي كتقريب
                                'comment': 'BUY',  # افتراضياً نعتبرها شراء
                                'identifier': asset  # استخدام العملة كمعرف للمركز
                            }
                            
                            # تحويل إلى صيغة _asdict() المشابهة لـ MT5
                            class Position:
                                def __init__(self, **kwargs):
                                    for key, value in kwargs.items():
                                        setattr(self, key, value)
                                
                                def _asdict(self):
                                    return {key: value for key, value in self.__dict__.items()}
                            
                            positions.append(Position(**position_data))
            
            return positions if positions else None
            
        except Exception as e:
            logger.error(f"خطأ في استرجاع المراكز المفتوحة: {e}")
            return None
    
    def order_send(self, request):
        """
        إرسال طلب تداول - يحاكي order_send في MT5
        """
        try:
            symbol = request.get('symbol')
            action = request.get('action')
            order_type = request.get('type')
            volume = request.get('volume')
            price = request.get('price')
            position = request.get('position')  # للإغلاق
            sl = request.get('sl')
            tp = request.get('tp')
            comment = request.get('comment')
            
            # تنسيق الكمية والسعر
            formatted_qty = self._format_quantity(symbol, volume)
            
            # تحديد نوع الطلب (شراء/بيع)
            side = SIDE_BUY
            if (order_type == self.ORDER_TYPE_BUY and action == self.TRADE_ACTION_DEAL) or \
               (order_type == self.ORDER_TYPE_SELL and action == self.TRADE_ACTION_DEAL and position is not None):
                side = SIDE_BUY
            else:
                side = SIDE_SELL
            
            result = None
            
            if self.account_type == 'futures':
                # للعقود المستقبلية
                
                # تعيين الرافعة المالية
                self.set_leverage(symbol)
                
                if action == self.TRADE_ACTION_DEAL:
                    # طلب فوري
                    if position is not None:
                        # إغلاق مركز
                        order = self.client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type=ORDER_TYPE_MARKET,
                            quantity=formatted_qty,
                            reduceOnly=True
                        )
                    else:
                        # فتح مركز جديد
                        order = self.client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type=ORDER_TYPE_MARKET,
                            quantity=formatted_qty
                        )
                        
                        # إضافة أوامر جني الأرباح ووقف الخسارة إذا تم تحديدهما
                        if sl is not None:
                            stop_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
                            self.client.futures_create_order(
                                symbol=symbol,
                                side=stop_side,
                                type=ORDER_TYPE_STOP_MARKET,
                                stopPrice=self._format_price(symbol, sl),
                                closePosition=True
                            )
                        
                        if tp is not None:
                            take_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
                            self.client.futures_create_order(
                                symbol=symbol,
                                side=take_side,
                                type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                                stopPrice=self._format_price(symbol, tp),
                                closePosition=True
                            )
                
                result = order
            else:
                # للتداول الفوري
                if action == self.TRADE_ACTION_DEAL:
                    # طلب فوري
                    order = self.client.create_order(
                        symbol=symbol,
                        side=side,
                        type=ORDER_TYPE_MARKET,
                        quantity=formatted_qty
                    )
                    
                    # لا يمكن وضع وقف خسارة أو جني أرباح مباشرة في Spot
                    # يجب استخدام أوامر OCO منفصلة إذا كان ذلك مطلوباً
                    
                    result = order
            
            # تحويل النتيجة إلى صيغة MT5
            if result:
                # تحضير البيانات
                result_data = {
                    'retcode': 0,  # النجاح
                    'deal': result.get('orderId'),
                    'order': result.get('orderId'),
                    'volume': float(formatted_qty),
                    'price': float(result.get('price', price)),
                    'bid': 0,
                    'ask': 0,
                    'comment': comment,
                    'request': request,
                    'type': order_type,
                    'type_filling': request.get('type_filling'),
                    'type_time': request.get('type_time'),
                    'state': 'FILLED',
                    'time_expiration': 0,
                    'time_done': int(time.time() * 1000),
                    'time_setup': int(time.time() * 1000),
                    'time_setup_msc': int(time.time() * 1000)
                }
                
                # تحويل إلى صيغة _asdict() المشابهة لـ MT5
                class OrderResult:
                    def __init__(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)
                    
                    def _asdict(self):
                        return {key: value for key, value in self.__dict__.items()}
                
                return OrderResult(**result_data)
            else:
                # في حالة الفشل
                result_data = {
                    'retcode': 10009,  # فشل
                    'comment': 'فشل إرسال الطلب'
                }
                
                class OrderResult:
                    def __init__(self, **kwargs):
                        for key, value in kwargs.items():
                            setattr(self, key, value)
                    
                    def _asdict(self):
                        return {key: value for key, value in self.__dict__.items()}
                
                return OrderResult(**result_data)
            
        except BinanceAPIException as e:
            logger.error(f"خطأ في إرسال الطلب: {e}")
            
            # في حالة الخطأ
            result_data = {
                'retcode': 10009,  # فشل
                'comment': f'خطأ: {str(e)}'
            }
            
            class OrderResult:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                
                def _asdict(self):
                    return {key: value for key, value in self.__dict__.items()}
            
            return OrderResult(**result_data)
    
    # ثوابت تحاكي ثوابت MT5
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_MODIFY = 7
    TRADE_ACTION_REMOVE = 8
    TRADE_ACTION_CLOSE_BY = 9
    
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    
    ORDER_FILLING_FOK = 1
    ORDER_FILLING_IOC = 2
    
    ORDER_TIME_GTC = 1
    
    def get_current_price(self, symbol):
        """
        الحصول على السعر الحالي للرمز
        """
        try:
            if self.account_type == 'futures':
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
            else:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
            
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"خطأ في الحصول على السعر الحالي: {e}")
            return 0