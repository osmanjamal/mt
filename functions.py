from flask import Flask, request, render_template, redirect, url_for, flash
import json
import datetime
import logging

# إعداد التسجيل لتتبع الأخطاء والعمليات
logger = logging.getLogger("BinanceBot_Functions")

def ip_address():
    """
    استرجاع عنوان IP للمستخدم
    """
    try:
        if 'X-Forwarded-For' in request.headers:
            proxy_data = request.headers['X-Forwarded-For']
            ip_list = proxy_data.split(',')
            user_ip = ip_list[0]  # العنوان الأول في القائمة هو IP المستخدم
            user_ip = user_ip.replace(".", "")
        else:
            user_ip = request.remote_addr  # للتطوير المحلي
            user_ip = user_ip.replace(".", "")
        return user_ip
    except Exception as e:
        logger.error(f"خطأ في استرجاع عنوان IP: {e}")
        return "00000000"

def fetch_database(db_name):
    """
    قراءة قاعدة البيانات من ملف
    """
    try:
        read_data = database_read(db_name)
        data = read_data.replace("'", '"')
        data = json.loads(data)
        return data
    except Exception as e:
        logger.error(f"خطأ في قراءة قاعدة البيانات {db_name}: {e}")
        return {}

def database_read(file_name):
    """
    قراءة محتوى ملف
    """
    try:
        with open(file_name, "r", encoding="utf-8") as sincefile:
            since_date = sincefile.read()
        return since_date
    except Exception as e:
        logger.error(f"خطأ في قراءة الملف {file_name}: {e}")
        return "{}"

def write_signal_data(order_time, action, symbol, price, tp, sl, qty, qty_type):
    """
    كتابة بيانات الإشارة إلى ملف signals.json
    """
    try:
        # قراءة الملف الحالي أو إنشاء قائمة جديدة إذا لم يكن موجوداً
        try:
            with open('signals.json', 'r', encoding='utf-8') as f:
                trade_data = json.load(f)
        except FileNotFoundError:
            trade_data = []
        
        # إضافة البيانات الجديدة
        trade_data.append({
            'order_time': order_time,
            'action': action,
            'symbol': symbol,
            'entry': price,
            'tp': tp,
            'sl': sl,
            'qty': qty,
            'qty_type': qty_type
        })

        # كتابة البيانات المحدثة للملف
        with open('signals.json', 'w', encoding='utf-8') as f:
            json.dump(trade_data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"تم تسجيل إشارة جديدة لـ {symbol}")
        return True
    except Exception as e:
        logger.error(f"خطأ في كتابة بيانات الإشارة: {e}")
        return False

def write_trade_data(order_id, order_time, action, symbol, price, qty):
    """
    كتابة بيانات الصفقة إلى ملف trades.json
    """
    try:
        # قراءة الملف الحالي أو إنشاء قائمة جديدة إذا لم يكن موجوداً
        try:
            with open('trades.json', 'r', encoding='utf-8') as f:
                trade_data = json.load(f)
        except FileNotFoundError:
            trade_data = []
        
        # إضافة البيانات الجديدة
        trade_data.append({
            'order_time': order_time,
            'order_id': order_id,
            'action': action,
            'symbol': symbol,
            'price': price,
            'qty': qty
        })

        # كتابة البيانات المحدثة للملف
        with open('trades.json', 'w', encoding='utf-8') as f:
            json.dump(trade_data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"تم تسجيل صفقة جديدة برقم {order_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في كتابة بيانات الصفقة: {e}")
        return False

def delete_duplicates_with_symbol(trade_data, symbol):
    """
    حذف التكرارات في البيانات مع الاحتفاظ بواحدة فقط لكل رمز
    """
    unique_data = []
    symbol_found = False

    for trade in trade_data:
        if trade.get('symbol') == symbol:
            if not symbol_found:
                symbol_found = True
                unique_data.append(trade)
        else:
            unique_data.append(trade)

    return unique_data

def read(file_name):
    """
    قراءة محتوى ملف
    """
    try:
        with open(file_name, "r+", encoding="utf-8") as file:
            read_file = file.read()
        return read_file
    except Exception as e:
        logger.error(f"خطأ في قراءة الملف {file_name}: {e}")
        return ""

def write(file_name, data):
    """
    كتابة بيانات إلى ملف
    """
    try:
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(str(data))
        return True
    except Exception as e:
        logger.error(f"خطأ في كتابة البيانات إلى الملف {file_name}: {e}")
        return False

def truncate_float(number):
    """
    اقتطاع الرقم العشري إلى منزلتين عشريتين
    """
    try:
        number_str = str(number)
        if '.' in number_str:
            integer_part, decimal_part = number_str.split('.')
            truncated_decimal = decimal_part[:2]
            truncated_str = f"{integer_part}.{truncated_decimal}"
            truncated_float = float(truncated_str)
            return truncated_float
        return number
    except Exception as e:
        logger.error(f"خطأ في اقتطاع الرقم العشري: {e}")
        return number

def print_dict_data(data, output):
    """
    طباعة بيانات القاموس
    """
    for key, value in data.items():
        output.append(f"{key} : {value}")

def log_value(value):
    """
    تسجيل قيمة في ملف max_loss.txt
    """
    try:
        with open('max_loss.txt', 'a', encoding="utf-8") as file:
            file.write(f'{value}\n')
        return True
    except Exception as e:
        logger.error(f"خطأ في تسجيل القيمة: {e}")
        return False

def check_trade():
    """
    التحقق من إمكانية التداول بناءً على خسائر متتالية
    """
    try:
        trade = True
        consecutive_negative = 0
        try:
            with open('max_loss.txt', 'r', encoding="utf-8") as file:
                for line in file:
                    value = float(line.strip())
                    if value < 0:
                        consecutive_negative += 1
                        max_consecutive_loss = read('max_loss_value.txt')
                        if max_consecutive_loss != '':
                            if consecutive_negative == float(max_consecutive_loss):
                                trade = False
                                return trade
                    else:
                        consecutive_negative = 0
        except FileNotFoundError:
            # الملف غير موجود، يمكن التداول
            return True

        return trade
    except Exception as e:
        logger.error(f"خطأ في التحقق من إمكانية التداول: {e}")
        return True  # في حالة الخطأ، نسمح بالتداول افتراضياً

def update_config(index_1, value_1, index_2, value_2, index_3, value_3):
    """
    تحديث ملف الإعدادات
    """
    try:
        with open('config.py', 'r', encoding="utf-8") as file:
            lines = file.readlines()

        modified_lines = []
        for line in lines:
            if line.startswith(index_1):
                modified_lines.append(f"{index_1}'{value_1}'\n")
            elif line.startswith(index_2):
                modified_lines.append(f"{index_2}'{value_2}'\n")
            elif line.startswith(index_3):
                modified_lines.append(f"{index_3}'{value_3}'\n")
            else:
                modified_lines.append(line)
        
        with open('config.py', 'w', encoding="utf-8") as file:
            file.writelines(modified_lines)
        
        logger.info('تم تحديث بيانات الإعدادات بنجاح')
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث ملف الإعدادات: {e}")
        return False

def update_binance_config(api_key=None, api_secret=None, account_type=None, leverage=None, testnet=None):
    """
    تحديث إعدادات بايننس في ملف الإعدادات
    """
    try:
        with open('config.py', 'r', encoding="utf-8") as file:
            lines = file.readlines()

        # التحقق من وجود خطوط الإعدادات
        has_api_key = has_api_secret = has_account_type = has_leverage = has_testnet = False
        for line in lines:
            if line.startswith('binance_api_key = '):
                has_api_key = True
            elif line.startswith('binance_api_secret = '):
                has_api_secret = True
            elif line.startswith('account_type = '):
                has_account_type = True
            elif line.startswith('leverage = '):
                has_leverage = True
            elif line.startswith('binance_testnet = '):
                has_testnet = True

        modified_lines = []
        for line in lines:
            if line.startswith('binance_api_key = ') and api_key is not None:
                modified_lines.append(f"binance_api_key = '{api_key}'\n")
            elif line.startswith('binance_api_secret = ') and api_secret is not None:
                modified_lines.append(f"binance_api_secret = '{api_secret}'\n")
            elif line.startswith('account_type = ') and account_type is not None:
                modified_lines.append(f"account_type = '{account_type}'\n")
            elif line.startswith('leverage = ') and leverage is not None:
                modified_lines.append(f"leverage = {leverage}\n")
            elif line.startswith('binance_testnet = ') and testnet is not None:
                modified_lines.append(f"binance_testnet = {testnet}\n")
            else:
                modified_lines.append(line)
        
        # إضافة الإعدادات الغير موجودة
        if not has_api_key and api_key is not None:
            modified_lines.append(f"binance_api_key = '{api_key}'\n")
        if not has_api_secret and api_secret is not None:
            modified_lines.append(f"binance_api_secret = '{api_secret}'\n")
        if not has_account_type and account_type is not None:
            modified_lines.append(f"account_type = '{account_type}'\n")
        if not has_leverage and leverage is not None:
            modified_lines.append(f"leverage = {leverage}\n")
        if not has_testnet and testnet is not None:
            modified_lines.append(f"binance_testnet = {testnet}\n")
        
        with open('config.py', 'w', encoding="utf-8") as file:
            file.writelines(modified_lines)
        
        logger.info('تم تحديث إعدادات بايننس بنجاح')
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث إعدادات بايننس: {e}")
        return False

def get_binance_symbols(binance_client, account_type='futures'):
    """
    الحصول على قائمة الرموز المتاحة في بايننس
    """
    try:
        if binance_client and binance_client.client:
            if account_type == 'futures':
                exchange_info = binance_client.client.futures_exchange_info()
                symbols = [item['symbol'] for item in exchange_info['symbols'] if item['status'] == 'TRADING']
            else:
                exchange_info = binance_client.client.get_exchange_info()
                symbols = [item['symbol'] for item in exchange_info['symbols'] if item['status'] == 'TRADING']
            
            return symbols
        else:
            logger.error("العميل غير متصل ببايننس")
            return []
    except Exception as e:
        logger.error(f"خطأ في الحصول على قائمة الرموز: {e}")
        return []

def format_binance_symbol(symbol):
    """
    تنسيق الرمز ليتناسب مع صيغة بايننس
    """
    # إزالة الشرطات والمسافات
    formatted_symbol = symbol.replace("/", "").replace(" ", "")
    
    # تحويل USD إلى USDT إذا لزم الأمر
    if formatted_symbol.endswith("USD") and not formatted_symbol.endswith("USDT"):
        formatted_symbol = f"{formatted_symbol}T"
    
    return formatted_symbol

def calculate_quantity(binance_client, symbol, qty, qty_type='fixed'):
    """
    حساب الكمية المناسبة للتداول بناءً على نوع الكمية والرصيد
    """
    try:
        if not binance_client or not binance_client.client:
            logger.error("العميل غير متصل ببايننس")
            return qty
        
        if qty_type == 'percent':
            # حساب النسبة من الرصيد المتاح
            if binance_client.account_type == 'futures':
                account = binance_client.client.futures_account()
                balance = float(account['totalWalletBalance'])
                calculated_qty = (float(qty) / 100.0) * balance
            else:
                account = binance_client.client.get_account()
                usdt_balance = 0
                for balance in account['balances']:
                    if balance['asset'] == 'USDT':
                        usdt_balance = float(balance['free'])
                        break
                calculated_qty = (float(qty) / 100.0) * usdt_balance
            
            # الحصول على سعر الرمز
            current_price = 0
            try:
                if binance_client.account_type == 'futures':
                    ticker = binance_client.client.futures_mark_price(symbol=symbol)
                    current_price = float(ticker['markPrice'])
                else:
                    ticker = binance_client.client.get_symbol_ticker(symbol=symbol)
                    current_price = float(ticker['price'])
            except Exception as e:
                logger.error(f"خطأ في الحصول على سعر الرمز: {e}")
                return qty
            
            # حساب الكمية بناءً على القيمة والسعر
            if current_price > 0:
                calculated_qty = calculated_qty / current_price
            else:
                return qty
            
            # تنسيق الكمية حسب دقة الرمز
            precision = binance_client._get_quantity_precision(symbol)
            formatted_qty = f"{{:.{precision}f}}".format(calculated_qty)
            
            return float(formatted_qty)
        else:
            # إرجاع الكمية كما هي
            return float(qty)
    except Exception as e:
        logger.error(f"خطأ في حساب الكمية: {e}")
        return float(qty)

def get_account_balance(binance_client):
    """
    الحصول على رصيد الحساب
    """
    try:
        if not binance_client or not binance_client.client:
            logger.error("العميل غير متصل ببايننس")
            return 0
        
        if binance_client.account_type == 'futures':
            account = binance_client.client.futures_account()
            return float(account['totalWalletBalance'])
        else:
            account = binance_client.client.get_account()
            usdt_balance = 0
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    usdt_balance = float(balance['free'])
                    break
            return usdt_balance
    except Exception as e:
        logger.error(f"خطأ في الحصول على رصيد الحساب: {e}")
        return 0
