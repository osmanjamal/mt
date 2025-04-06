from main import app, binance_trader
from flask import render_template, request, redirect, url_for, flash
import config
import importlib
from functions import *
import pandas as pd
import logging

# إعداد التسجيل لتتبع الأخطاء والعمليات
logger = logging.getLogger("BinanceBot_Routes")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    مسار تسجيل الدخول للمشرف
    """
    error = ''

    if request.method == 'POST':
        if request.form.get('username') != config.admin_username or \
                request.form.get('password') != config.admin_password:
            error = 'بيانات غير صحيحة. الرجاء المحاولة مرة أخرى.'
            flash(format('بيانات غير صحيحة. الرجاء المحاولة مرة أخرى.'), 'error')
        else:
            write('auth.txt', 'authenticated')
            write('ip_address.txt', ip_address())
            return redirect(url_for('index'))
    return render_template('login.html', error=error)

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    """
    مسار تسجيل الخروج
    """
    write('auth.txt', 'unauthenticated')
    write('ip_address.txt', '')
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def main():
    """
    المسار الرئيسي، يتحقق من المصادقة
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()
    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('index'))

@app.route('/password_reset', methods=['POST'])
def reset_password():
    """
    مسار إعادة تعيين كلمة المرور
    """
    if request.method == 'POST':
        admin_username = request.form.get('current_username')
        old_pass = request.form.get('current_password')
        new_pass = request.form.get('new_password')
        if admin_username == config.admin_username:
            if old_pass == config.admin_password:
                config.admin_password = new_pass
                with open('config.py', 'r', encoding='utf-8') as f:
                    config_contents = f.read()
                new_config_contents = config_contents.replace(
                    f"admin_password = '{old_pass}'", f"admin_password = '{new_pass}'")
                with open('config.py', 'w', encoding='utf-8') as f:
                    f.write(new_config_contents)
                    flash(format('تم تغيير كلمة مرور المشرف بنجاح'), 'success')
            else:
                flash(format('كلمة المرور الحالية غير صحيحة'), 'error')
        else:
            flash(format('اسم المستخدم غير صحيح'), 'error')
    return redirect(url_for('change_password'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """
    مسار صفحة تغيير كلمة المرور
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()
    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    return render_template('change_password.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def index():
    """
    مسار لوحة التحكم الرئيسية
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        script_type = request.form.get('script_type', "")
        quantity = request.form.get('qty', "")
        symbol = request.form.get('symbol', "")
        alert_type = request.form.get('alert_type', "")
        tp_i = request.form.get('tp_distance', "0")
        sl_i = request.form.get('sl_distance', "0")

        if script_type == 'INDICATOR':
            if alert_type == 'BUY':
                syntax = '{</br>"symbol": ' + '"' + symbol + '",\
                            </br>"qty": ' + '"' + quantity + '",\
                            </br>"action": "buy",\
                            </br>"market_position": "long",\
                            </br>"tp": ' + '"' + tp_i + '",\
                            </br>"sl": ' + '"' + sl_i + '",\
                            </br>"price": "{{close}}"</br>''}'

            elif alert_type == 'SELL':
                syntax = '{</br>"symbol": ' + '"' + symbol + '",\
                            </br>"qty": ' + '"' + quantity + '",\
                            </br>"action": "sell",\
                            </br>"market_position": "short",\
                            </br>"tp": ' + '"' + tp_i + '",\
                            </br>"sl": ' + '"' + sl_i + '",\
                            </br>"price": "{{close}}"</br>''}'
                
        elif script_type == 'STRATEGY':
            syntax = '{</br>"symbol": ' + '"' + symbol + '",\
                    </br>"qty": ' + '"' + quantity + '",\
                    </br>"action": "{{strategy.order.action}}",\
                    </br>"market_position": "{{strategy.market_position}}",\
                    </br>"tp": ' + '"' + tp_i + '",\
                    </br>"sl": ' + '"' + sl_i + '",\
                    </br>"price": "{{close}}"</br>''}'

        return render_template('index.html', syntax=syntax)
    else:
        return render_template('index.html')

@app.route('/signals', methods=['GET', 'POST'])
def signals():
    """
    مسار عرض سجل الإشارات
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()
        
    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    try:
        with open('signals.json', 'r') as f:
            trade_data = json.load(f)
            df = pd.DataFrame(
                trade_data,
                columns=['order_time', 'symbol', 'action', 'entry', 'tp', 'sl', 'qty', 'qty_type'])
            df.rename(columns={
                'order_time': 'التوقيت',
                'symbol': 'الرمز',
                'action': 'الاتجاه',
                'qty': 'الكمية',
                'entry': 'سعر الدخول',
                'tp': 'جني الأرباح',
                'sl': 'وقف الخسارة',
                'qty_type': 'نوع الحساب'
            }, inplace=True)
            df = df.sort_values(by="التوقيت", ascending=False)
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الإشارات: {e}")
        df = pd.DataFrame(columns=['التوقيت', 'الرمز', 'الاتجاه', 'الكمية', 'سعر الدخول', 'جني الأرباح', 'وقف الخسارة', 'نوع الحساب'])

    return render_template('signals.html',
                            tables=[df.to_html(classes='data')],
                            titles=df.columns.values)

@app.route('/trades', methods=['GET', 'POST'])
def trades():
    """
    مسار عرض سجل الصفقات
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    try:
        with open('trades.json', 'r') as f:
            trade_data = json.load(f)
            df = pd.DataFrame(
                trade_data,
                columns=['order_time', 'order_id', 'symbol', 'action', 'price', 'qty'])
            df.rename(columns={
                'order_time': 'التوقيت',
                'order_id': 'رقم الطلب',
                'symbol': 'الرمز',
                'action': 'الاتجاه',
                'qty': 'الكمية',
                'price': 'السعر'
            }, inplace=True)
            df = df.sort_values(by="التوقيت", ascending=False)
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف الصفقات: {e}")
        df = pd.DataFrame(columns=['التوقيت', 'رقم الطلب', 'الرمز', 'الاتجاه', 'الكمية', 'السعر'])

    return render_template('trades.html',
                            tables=[df.to_html(classes='data')],
                            titles=df.columns.values)

@app.route('/max_loss_settings', methods=['GET', 'POST'])
def max_loss_settings():
    """
    مسار إعدادات الحد الأقصى للخسارة
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    max_loss_value = read('max_loss_value.txt')
    if len(max_loss_value) > 0:
        max_loss_value = max_loss_value
    else:
        max_loss_value = 0

    if request.method == 'POST':
        max_loss_value = request.form.get('max_loss', "")
        if len(max_loss_value) > 0:
            write('max_loss_value.txt', max_loss_value)
        if max_loss_value == '':
            max_loss_value = 0
        return render_template('settings.html', max_loss_value=max_loss_value)

    return render_template('settings.html', max_loss_value=max_loss_value)

@app.route('/reset_max_loss', methods=['GET', 'POST'])
def reset_max_loss():
    """
    مسار إعادة تعيين الحد الأقصى للخسارة
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        write('max_loss.txt', '')
        return redirect(url_for('max_loss_settings'))

def get_display_data(value, default='لا يوجد'):
    """
    تنسيق البيانات للعرض مع إخفاء جزء منها
    """
    if len(value) > 0:
        return value[:len(value) - 5] + '************'
    else:
        return default

@app.route('/binance_settings', methods=['GET', 'POST'])
def binance_settings():
    """
    مسار إعدادات API بايننس - جديد
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    importlib.reload(config)

    # جلب الإعدادات الحالية من ملف config
    api_key = getattr(config, 'binance_api_key', '')
    api_secret = getattr(config, 'binance_api_secret', '')
    account_type = getattr(config, 'account_type', 'futures')
    leverage = getattr(config, 'leverage', 10)
    testnet = getattr(config, 'binance_testnet', False)

    # إخفاء جزء من المفاتيح السرية للعرض
    if api_key:
        display_api_key = api_key[:5] + '********' + api_key[-5:] if len(api_key) > 10 else '********'
    else:
        display_api_key = ''
    
    display_api_secret = '************************' if api_secret else ''

    return render_template('binance_settings.html',
                          api_key=display_api_key,
                          api_secret=display_api_secret,
                          account_type=account_type,
                          leverage=leverage,
                          testnet=testnet)

@app.route('/add_binance_api', methods=['POST'])
def add_binance_api():
    """
    مسار إضافة/تحديث بيانات API بايننس - جديد
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        api_key = request.form.get('api_key', '')
        api_secret = request.form.get('api_secret', '')
        account_type = request.form.get('account_type', 'futures')
        leverage = request.form.get('leverage', '10')
        testnet = request.form.get('testnet', 'False') == 'True'
        
        # تحديث ملف الإعدادات
        try:
            with open('config.py', 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            # البحث عن الإعدادات الحالية أو إضافتها إذا لم تكن موجودة
            has_api_key = has_api_secret = has_account_type = has_leverage = has_testnet = False
            modified_lines = []
            
            for line in lines:
                if line.startswith('binance_api_key = '):
                    if api_key:  # تحديث فقط إذا تم إدخال قيمة جديدة
                        modified_lines.append(f"binance_api_key = '{api_key}'\n")
                    else:
                        modified_lines.append(line)
                    has_api_key = True
                elif line.startswith('binance_api_secret = '):
                    if api_secret:  # تحديث فقط إذا تم إدخال قيمة جديدة
                        modified_lines.append(f"binance_api_secret = '{api_secret}'\n")
                    else:
                        modified_lines.append(line)
                    has_api_secret = True
                elif line.startswith('account_type = '):
                    modified_lines.append(f"account_type = '{account_type}'\n")
                    has_account_type = True
                elif line.startswith('leverage = '):
                    modified_lines.append(f"leverage = {leverage}\n")
                    has_leverage = True
                elif line.startswith('binance_testnet = '):
                    modified_lines.append(f"binance_testnet = {testnet}\n")
                    has_testnet = True
                else:
                    modified_lines.append(line)
            
            # إضافة الإعدادات التي لم تكن موجودة
            if not has_api_key and api_key:
                modified_lines.append(f"binance_api_key = '{api_key}'\n")
            if not has_api_secret and api_secret:
                modified_lines.append(f"binance_api_secret = '{api_secret}'\n")
            if not has_account_type:
                modified_lines.append(f"account_type = '{account_type}'\n")
            if not has_leverage:
                modified_lines.append(f"leverage = {leverage}\n")
            if not has_testnet:
                modified_lines.append(f"binance_testnet = {testnet}\n")
            
            # كتابة التعديلات للملف
            with open('config.py', 'w', encoding='utf-8') as file:
                file.writelines(modified_lines)
            
            flash(format('تم تحديث إعدادات بايننس بنجاح'), 'success')
            
            # إعادة تهيئة BinanceTrader
            try:
                importlib.reload(config)
                binance_trader.__init__()
                if binance_trader.initialize():
                    flash(format('تم الاتصال ببايننس بنجاح'), 'success')
                else:
                    flash(format('فشل الاتصال ببايننس، تحقق من البيانات'), 'error')
            except Exception as e:
                flash(format(f'خطأ في إعادة الاتصال ببايننس: {str(e)}'), 'error')
                logger.error(f"خطأ في إعادة تهيئة BinanceTrader: {e}")
        
        except Exception as e:
            flash(format(f'خطأ في تحديث الإعدادات: {str(e)}'), 'error')
            logger.error(f"خطأ في تحديث ملف config.py: {e}")
    
    return redirect(url_for('binance_settings'))

@app.route('/balance_info', methods=['GET'])
def balance_info():
    """
    مسار عرض معلومات الرصيد في بايننس - جديد
    """
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    try:
        # جلب معلومات الحساب من بايننس
        if binance_trader.client:
            if binance_trader.account_type == 'futures':
                account = binance_trader.client.futures_account()
                
                # استخراج البيانات المهمة
                balance_data = {
                    'نوع الحساب': 'العقود المستقبلية',
                    'الرصيد الكلي': f"{float(account['totalWalletBalance']):.8f} USDT",
                    'الهامش المتاح': f"{float(account['availableBalance']):.8f} USDT",
                    'الهامش المستخدم': f"{float(account['totalMaintMargin']):.8f} USDT",
                    'الربح/الخسارة المفتوحة': f"{float(account['totalUnrealizedProfit']):.8f} USDT",
                }
                
                # استخراج المراكز المفتوحة
                positions = []
                for pos in account['positions']:
                    if float(pos['positionAmt']) != 0:
                        pos_data = {
                            'الرمز': pos['symbol'],
                            'الاتجاه': 'شراء' if float(pos['positionAmt']) > 0 else 'بيع',
                            'الكمية': abs(float(pos['positionAmt'])),
                            'سعر الدخول': float(pos['entryPrice']),
                            'السعر الحالي': float(pos['markPrice']),
                            'الربح/الخسارة': float(pos['unrealizedProfit']),
                            'الرافعة المالية': pos['leverage'],
                        }
                        positions.append(pos_data)
            else:
                # للتداول الفوري
                account = binance_trader.client.get_account()
                
                # استخراج البيانات المهمة
                balances = []
                for balance in account['balances']:
                    free = float(balance['free'])
                    locked = float(balance['locked'])
                    if free > 0 or locked > 0:
                        # محاولة الحصول على سعر العملة بالدولار
                        try:
                            if balance['asset'] != 'USDT':
                                ticker = binance_trader.client.get_symbol_ticker(symbol=f"{balance['asset']}USDT")
                                price = float(ticker['price'])
                                value = (free + locked) * price
                            else:
                                price = 1
                                value = free + locked
                            
                            balances.append({
                                'العملة': balance['asset'],
                                'المتاح': free,
                                'المحجوز': locked,
                                'الإجمالي': free + locked,
                                'السعر بالدولار': price,
                                'القيمة بالدولار': value
                            })
                        except:
                            # إذا لم يمكن الحصول على السعر
                            balances.append({
                                'العملة': balance['asset'],
                                'المتاح': free,
                                'المحجوز': locked,
                                'الإجمالي': free + locked,
                                'السعر بالدولار': 'غير متاح',
                                'القيمة بالدولار': 'غير متاح'
                            })
                
                # حساب إجمالي القيمة بالدولار
                total_value = sum([b['القيمة بالدولار'] for b in balances if isinstance(b['القيمة بالدولار'], (int, float))])
                
                balance_data = {
                    'نوع الحساب': 'التداول الفوري',
                    'إجمالي القيمة بالدولار': f"{total_value:.2f} USDT",
                }
                
                # تحويل balances إلى جدول
                positions = balances
            
            return render_template('balance_info.html',
                                  balance_data=balance_data,
                                  positions=positions)
        else:
            flash(format('لم يتم الاتصال ببايننس، تحقق من إعدادات API'), 'error')
            return redirect(url_for('binance_settings'))
    
    except Exception as e:
        flash(format(f'خطأ في جلب معلومات الرصيد: {str(e)}'), 'error')
        logger.error(f"خطأ في جلب معلومات الرصيد: {e}")
        return redirect(url_for('index'))