import json
from flask import Flask, request, render_template, redirect, url_for, flash
import os
import importlib
import concurrent.futures as cf
import datetime
import config
import time as t
from flask import Flask, request, render_template, redirect, url_for, flash
import pandas as pd
import logging
from binance_client import BinanceTrader

# إعداد التسجيل لتتبع الأخطاء والعمليات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("webapp.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("BinanceBot")

# إنشاء مثيل من BinanceTrader بدلاً من MT5
binance_trader = BinanceTrader()
if not binance_trader.initialize():
    logger.error("فشل في تهيئة الاتصال ببايننس")
else:
    logger.info("تم تهيئة الاتصال ببايننس بنجاح")

app = Flask(__name__)
app.config['SECRET_KEY'] = '123fdsgcsfgxgfg1514cgcd45'

# استيراد الوظائف المساعدة
from functions import print_dict_data, write_signal_data, read, write, ip_address

@app.route("/webhook", methods=["POST"])
def webhook_user():
    """
    معالجة طلبات webhook من TradingView
    """
    output = []
    
    try:
        data_str = request.data.decode('utf-8')
        logger.info(f"بيانات واردة: {data_str}")
        output.append(data_str)
        
        data = json.loads(data_str)
        output.append("-------------------------------------------------------------------------")
        output.append(f"-------------------  WEBHOOK USER REQUEST  ----------------------------")
        output.append("-------------------------------------------------------------------------")
        
        # تسجيل وقت الإشارة
        dt = datetime.datetime.now()
        signal_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        output.append(f'| Signal Time : {signal_time}')
        
        # طباعة بيانات الطلب
        print_dict_data(data, output)
        
        # معالجة الطلب في مؤشر ترابط منفصل
        with cf.ThreadPoolExecutor(max_workers=2 * os.cpu_count()) as executor:
            future = executor.submit(binance_function, data, output)
        
        return "Request Processed"
    
    except Exception as e:
        error_msg = f"خطأ في معالجة الطلب: {str(e)}"
        logger.error(error_msg)
        output.append(error_msg)
        
        # حفظ المخرجات في ملف
        with open("output.txt", "a", encoding="utf-8") as output_file:
            for line in output:
                output_file.write(line + "\n")
        
        return "Error Processing Request", 400


def binance_function(data, output):
    """
    معالجة إشارة التداول باستخدام BinanceTrader بدلاً من MT5
    """
    try:
        # الحصول على معلومات الحساب
        account_info = binance_trader.account_info()._asdict()
        which_account = account_info.get('login', 'unknown')
        
        # استخراج البيانات من الإشارة
        ACTION = data["action"].upper()
        
        # تعديل رمز التداول ليتناسب مع بايننس
        SYMBOL = data["symbol"].replace("/", "")  # إزالة الشرطات من الرموز مثل BTC/USDT
        if SYMBOL.endswith("USD") and not SYMBOL.endswith("USDT"):
            SYMBOL = f"{SYMBOL}T"  # تحويل USD إلى USDT إذا لزم الأمر
        
        # معالجة الكمية
        QTY = float(data["qty"])
        qty_type = data.get("qty_type", "fixed").lower()
        
        # حساب الكمية بناءً على النوع (نسبة أو قيمة ثابتة)
        if qty_type == "percent":
            if binance_trader.account_type == "futures":
                # للعقود المستقبلية، نحسب النسبة من إجمالي الرصيد
                balance = float(account_info['balance'])
                QTY = (QTY / 100.0) * balance
            else:
                # للتداول الفوري، نحسب النسبة من رصيد USDT
                balances = binance_trader.client.get_account()['balances']
                usdt_balance = 0
                for balance in balances:
                    if balance['asset'] == 'USDT':
                        usdt_balance = float(balance['free'])
                        break
                QTY = (QTY / 100.0) * usdt_balance
        
        # استخراج مستويات جني الأرباح ووقف الخسارة
        try:
            tp = float(data.get("tp", 0))
        except:
            tp = 0
        
        try:
            sl = float(data.get("sl", 0))
        except:
            sl = 0
        
        # استخراج اتجاه السوق ونوع الطلب
        market_position = data.get("market_position", "flat")
        price = float(data.get("price", 0))
        
        # إذا لم يتم تحديد السعر، نحصل على السعر الحالي
        if price == 0:
            price = binance_trader.get_current_price(SYMBOL)
        
        order_response = None
        
        # تنفيذ الإشارة بناءً على الإجراء واتجاه السوق
        if ACTION == "BUY" and market_position == "long":
            logger.info(f"تنفيذ أمر شراء للرمز {SYMBOL}")
            try:
                # إغلاق أي مراكز بيع مفتوحة أولاً
                positions = binance_trader.positions_get(SYMBOL)
                if positions:
                    for position in positions:
                        pos_dict = position._asdict()
                        if pos_dict.get('comment') == 'SELL':
                            # إغلاق المركز
                            close_request = {
                                "action": binance_trader.TRADE_ACTION_DEAL,
                                "symbol": SYMBOL,
                                "volume": pos_dict.get('volume', 0),
                                "type": binance_trader.ORDER_TYPE_BUY,
                                "position": pos_dict.get('identifier'),
                                "price": price,
                                "comment": "إغلاق المركز السابق",
                                "type_time": binance_trader.ORDER_TIME_GTC,
                                "type_filling": binance_trader.ORDER_FILLING_FOK,
                            }
                            binance_trader.order_send(close_request)
                
                # فتح مركز شراء جديد
                if tp != 0 and sl != 0:
                    # حساب مستويات جني الأرباح ووقف الخسارة
                    tp_price = price * (1 + (tp/100))
                    sl_price = price * (1 - (sl/100))
                else:
                    tp_price = None
                    sl_price = None
                
                # إنشاء طلب الشراء
                buy_request = {
                    "action": binance_trader.TRADE_ACTION_DEAL,
                    "symbol": SYMBOL,
                    "volume": abs(QTY),
                    "type": binance_trader.ORDER_TYPE_BUY,
                    "price": price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "comment": "BUY",
                    "type_time": binance_trader.ORDER_TIME_GTC,
                    "type_filling": binance_trader.ORDER_FILLING_FOK,
                }
                order_response = binance_trader.order_send(buy_request)
                
            except Exception as e:
                error_msg = f"خطأ في تنفيذ أمر الشراء: {str(e)}"
                logger.error(error_msg)
                output.append(error_msg)
        
        # إغلاق المركز الطويل
        elif ACTION == "BUY" and market_position == 'flat':
            logger.info(f"إغلاق أي مراكز بيع مفتوحة للرمز {SYMBOL}")
            try:
                positions = binance_trader.positions_get(SYMBOL)
                if positions:
                    for position in positions:
                        pos_dict = position._asdict()
                        if pos_dict.get('comment') == 'SELL':
                            # إغلاق المركز
                            close_request = {
                                "action": binance_trader.TRADE_ACTION_DEAL,
                                "symbol": SYMBOL,
                                "volume": pos_dict.get('volume', 0),
                                "type": binance_trader.ORDER_TYPE_BUY,
                                "position": pos_dict.get('identifier'),
                                "price": price,
                                "comment": "إغلاق المركز",
                                "type_time": binance_trader.ORDER_TIME_GTC,
                                "type_filling": binance_trader.ORDER_FILLING_FOK,
                            }
                            order_response = binance_trader.order_send(close_request)
            except Exception as e:
                error_msg = f"خطأ في إغلاق المركز: {str(e)}"
                logger.error(error_msg)
                output.append(error_msg)
        
        # فتح مركز بيع
        elif ACTION == "SELL" and market_position == "short":
            logger.info(f"تنفيذ أمر بيع للرمز {SYMBOL}")
            try:
                # إغلاق أي مراكز شراء مفتوحة أولاً
                positions = binance_trader.positions_get(SYMBOL)
                if positions:
                    for position in positions:
                        pos_dict = position._asdict()
                        if pos_dict.get('comment') == 'BUY':
                            # إغلاق المركز
                            close_request = {
                                "action": binance_trader.TRADE_ACTION_DEAL,
                                "symbol": SYMBOL,
                                "volume": pos_dict.get('volume', 0),
                                "type": binance_trader.ORDER_TYPE_SELL,
                                "position": pos_dict.get('identifier'),
                                "price": price,
                                "comment": "إغلاق المركز السابق",
                                "type_time": binance_trader.ORDER_TIME_GTC,
                                "type_filling": binance_trader.ORDER_FILLING_FOK,
                            }
                            binance_trader.order_send(close_request)
                
                # فتح مركز بيع جديد
                if tp != 0 and sl != 0:
                    # حساب مستويات جني الأرباح ووقف الخسارة
                    tp_price = price * (1 - (tp/100))
                    sl_price = price * (1 + (sl/100))
                else:
                    tp_price = None
                    sl_price = None
                
                # إنشاء طلب البيع
                sell_request = {
                    "action": binance_trader.TRADE_ACTION_DEAL,
                    "symbol": SYMBOL,
                    "volume": abs(QTY),
                    "type": binance_trader.ORDER_TYPE_SELL,
                    "price": price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "comment": "SELL",
                    "type_time": binance_trader.ORDER_TIME_GTC,
                    "type_filling": binance_trader.ORDER_FILLING_FOK,
                }
                order_response = binance_trader.order_send(sell_request)
                
            except Exception as e:
                error_msg = f"خطأ في تنفيذ أمر البيع: {str(e)}"
                logger.error(error_msg)
                output.append(error_msg)
        
        # إغلاق المركز القصير
        elif ACTION == "SELL" and market_position == 'flat':
            logger.info(f"إغلاق أي مراكز شراء مفتوحة للرمز {SYMBOL}")
            try:
                positions = binance_trader.positions_get(SYMBOL)
                if positions:
                    for position in positions:
                        pos_dict = position._asdict()
                        if pos_dict.get('comment') == 'BUY':
                            # إغلاق المركز
                            close_request = {
                                "action": binance_trader.TRADE_ACTION_DEAL,
                                "symbol": SYMBOL,
                                "volume": pos_dict.get('volume', 0),
                                "type": binance_trader.ORDER_TYPE_SELL,
                                "position": pos_dict.get('identifier'),
                                "price": price,
                                "comment": "إغلاق المركز",
                                "type_time": binance_trader.ORDER_TIME_GTC,
                                "type_filling": binance_trader.ORDER_FILLING_FOK,
                            }
                            order_response = binance_trader.order_send(close_request)
            except Exception as e:
                error_msg = f"خطأ في إغلاق المركز: {str(e)}"
                logger.error(error_msg)
                output.append(error_msg)
        
        # تسجيل تفاصيل الطلب
        output.append("--------------------------------------------------------------")
        output.append("------------------   ORDER DETAILS   -------------------------")
        output.append("--------------------------------------------------------------")
        
        try:
            dt = datetime.datetime.now()
            order_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            if order_response and hasattr(order_response, '_asdict'):
                order_dict = order_response._asdict()
                
                # حفظ بيانات الإشارة
                write_signal_data(order_time, ACTION, SYMBOL, price, tp, sl, QTY, which_account)
                
                # إضافة تفاصيل الطلب إلى المخرجات
                output.append(
                    f"| Order Placed ? Time : {order_time} \n| Side : {ACTION} \n| Symbol : {SYMBOL} \n| Entry : {price} \n| TP : {tp} "
                    f"\n| SL : {sl} \n| Qty : {QTY} \n| In Account : {which_account}"
                )
            else:
                output.append("No Order Placed")
                if order_response:
                    output.append(str(order_response))
        except Exception as e:
            error_msg = f"خطأ في تسجيل تفاصيل الطلب: {str(e)}"
            logger.error(error_msg)
            output.append("No Order Placed")
            output.append(error_msg)
        
        output.append("-------------------------------------------------------------")
        output.append("-------------------  END OF REQUEST  ------------------------")
        output.append("-------------------------------------------------------------")
        
        # حفظ المخرجات في ملف
        with open("output.txt", "a", encoding="utf-8") as output_file:
            for line in output:
                output_file.write(line + "\n")
        
        return {"code": "success", "message": "order executed"}
    
    except Exception as e:
        error_msg = f"خطأ عام في وظيفة binance_function: {str(e)}"
        logger.error(error_msg)
        output.append(error_msg)
        
        # حفظ المخرجات في ملف
        with open("output.txt", "a", encoding="utf-8") as output_file:
            for line in output:
                output_file.write(line + "\n")
        
        return {"code": "error", "message": str(e)}

# استيراد مسارات التطبيق
import routes

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True, threaded=True)