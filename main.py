import json
from flask import Flask, request, render_template, redirect, url_for,flash
import os
import importlib
import concurrent.futures as cf
import datetime
from mt5linux import MetaTrader5
import config
import time as t
from flask import Flask, request, render_template, redirect, url_for,flash
import pandas as pd

mt5 = MetaTrader5(host='localhost',port=8001)
mt5.initialize()
if not mt5.initialize():
    print("initialize() failed, error code =",mt5.last_error())

app = Flask(__name__)
app.config['SECRET_KEY'] = '123fdsgcsfgxgfg1514cgcd45'

@app.route("/webhook", methods=["POST"])
def webhook_user():
    output = []
    print(str(request.data))    
    output.append(str(request.data))
    data = json.loads(request.data)
    output.append("-------------------------------------------------------------------------")
    output.append(f"-------------------  WEBHOOK USER REQUEST  ----------------------------")
    output.append("-------------------------------------------------------------------------")
    try:
        dt = datetime.datetime.now()
        signal_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        output.append(f'| Signal Time : {signal_time}')
    except Exception as e:
        output.append(str(e))
        print(e)
    print_dict_data(data, output)
    print("-------------------------------------------------------------------------")

    with cf.ThreadPoolExecutor(max_workers=2 * os.cpu_count()) as executor:
        future = executor.submit(mt5_function, data, output)

    return "Request Processed"


def mt5_function(data,output):
    mt5 = MetaTrader5(host='localhost',port=8001)
    mt5.initialize()
    if not mt5.initialize():
        print("initialize() failed, error code =",mt5.last_error())
    which_account = mt5.account_info()._asdict()['login']
    ACTION = data["action"].upper()
    SYMBOL = data["symbol"]
    QTY = float(data["qty"])
    try:
        tp = float(data["tp"])
    except:
        tp = 0
    try:
        sl = float(data["sl"])
    except:
        sl = 0   
        
    # QTY = abs(QTY)
    qty_type = 'fixed'#data["qty_type"].lower()

    if qty_type == "percent":
        QTY = float(data["qty"]) / 100.00
    elif qty_type == "fixed":
        QTY = float(data["qty"])

    market_position = data["market_position"]
    price = float(data["price"])

    # print(price)
    if ACTION == "BUY" and market_position == "long":  # and trade_count < max_trades and entr_tp_check:
        try:
            order_response = close_positions_by_symbol(ACTION,SYMBOL)
        except Exception as e:
            print(e)
        try:
            order_response = place_order(ACTION,SYMBOL,abs(QTY),price,tp,sl)
        except Exception as e:
            print(e)

    ###################################################################################################
    if ACTION == "BUY" and market_position == 'flat':
        try:
            order_response = close_positions_by_symbol(ACTION,SYMBOL)
        except Exception as e:
            print(e)
    ###################################################################################################
    if ACTION == "SELL" and market_position == "short":  # and trade_count < max_trades and entr_tp_check:

        try:
            order_response = close_positions_by_symbol(ACTION,SYMBOL)
        except Exception as e:
            print(e)
        try:
            order_response = place_order(ACTION,SYMBOL,abs(QTY),price,tp,sl)
        except Exception as e:
            print(e)

    ###################################################################################################
    if ACTION == "SELL" and market_position == 'flat':
        try:
            order_response = close_positions_by_symbol(ACTION,SYMBOL)
        except Exception as e:
            print(e)
    ###################################################################################################

    output.append("--------------------------------------------------------------")
    output.append("------------------   ORDER DETAILS   -------------------------")
    output.append("--------------------------------------------------------------")
    try:
        dt = datetime.datetime.now()
        order_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        # print(order_response)
        if order_response:
            write_signal_data(order_time, ACTION, SYMBOL, price, tp, sl, QTY, which_account)
            output.append(
                f"| Order Placed ? Time : {order_time} \n| Side : {ACTION} \n| Symbol : {SYMBOL} \n| Entry : {price} \n| TP : {tp} \
            \n| SL : {sl} \n| Qty : {QTY} \n| In Account : {which_account}"
            )
    except Exception as e:
        output.append("No Order Placed")
        output.append(e)
    reversed_output = reversed(output)
    output.append("-------------------------------------------------------------")
    output.append("-------------------  END OF REQUEST  ------------------------")
    output.append("-------------------------------------------------------------")
    with open("output.txt", "a", encoding="utf-8") as output_file:
        for line in output:
            output_file.write(line + "\n")


    return {"code": "success", "message": "order executed"}


#########################################################################
#########################################################################
####################### FUNCTIONS.PY ####################################
#########################################################################
#########################################################################
#########################################################################


def ip_address():
    if 'X-Forwarded-For' in request.headers:
        proxy_data = request.headers['X-Forwarded-For']
        ip_list = proxy_data.split(',')
        user_ip = ip_list[0]  # first address in list is User IP
        user_ip = user_ip.replace(".","")
    else:
        user_ip = request.remote_addr  # For local development
        user_ip = user_ip.replace(".","")
    return user_ip

def tg_token():
    token = fetch_database('t_bot_token.json')
    token = token['bot_token']
    return token

def tg_channel():
    channel = fetch_database('t_bot_channel.json')
    channel = channel['channel']
    return channel

def fetch_database(db_name):
    try:
        read_data = database_read(db_name)
        data = read_data.replace("'", '"')
        data = json.loads(data)
        return data
    except Exception as e: print(e)

def database_read(file_name):
    sincefile = open(file_name, "r+")
    since_date = sincefile.read()
    sincefile.close()
    return since_date

def fetch_pos_data(positions,SYMBOL):
    for data in positions:
        #print(data)
        if SYMBOL in data['symbol']:
            if len(data) > 0:
                if len(data['symbol']) > 0:
                    if data['symbol'] == SYMBOL:
                        quantity = data['volume']
                        trade_price = data['openPrice']
    return quantity,trade_price

def write_signal_data(order_time, action,symbol,price,tp,sl,qty,qty_type):
    
    try:
        with open('signals.json', 'r') as f:
            trade_data = json.load(f)
    except FileNotFoundError:
        trade_data = []
    
    trade_data.append({'order_time': order_time, 'action': action,'symbol': symbol,'entry': price,
                        'tp':tp,'sl':sl,'qty': qty, 'qty_type': qty_type})

    # Write the updated trade data to the JSON file
    with open('signals.json', 'w') as f:
        json.dump(trade_data, f, indent=4)


def write_trade_data(order_id,order_time, action,symbol,price,qty):
    
    try:
        with open('trades.json', 'r') as f:
            trade_data = json.load(f)
    except FileNotFoundError:
        trade_data = []
    
    trade_data.append({'order_time': order_time, 'order_id': order_id,'action': action,'symbol': symbol,'price': price,
                        'qty': qty})

    # Write the updated trade data to the JSON file
    with open('trades.json', 'w') as f:
        json.dump(trade_data, f, indent=4)

def delete_duplicates_with_symbol(trade_data, symbol):
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
    file = open(file_name, "r+")
    read_file = file.read()
    file.close()
    return read_file


def write(file_name, data):
    file = open(file_name, "w")
    file.write(str(data))
    file.close()


def truncate_float(number):
    number_str = str(number)
    integer_part, decimal_part = number_str.split('.')
    truncated_decimal = decimal_part[:2]
    truncated_str = f"{integer_part}.{truncated_decimal}"
    truncated_float = float(truncated_str)
    return truncated_float


def print_dict_data(data,output):
    for key, value in data.items():
        output.append(f"{key} : {value}")

def log_value(value):
    with open('max_loss.txt', 'a') as file:
        file.write(f'{value}\n')

def check_trade():
    trade = True
    consecutive_negative = 0
    with open('max_loss.txt', 'r') as file:
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

    return trade

def update_config(index_1,value_1,index_2,value_2,index_3,value_3):
    with open('config.py', 'r') as file:
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
    
    with open('config.py', 'w') as file:
        file.writelines(modified_lines)
    
    print('MT5 credentials updated successfully.')
    
    with open('config.py', 'w') as file:
        file.writelines(modified_lines)
    
    

def update_Telegram(tg_token,tg_channel):
    with open('config.py', 'r') as file:
      lines = file.readlines()
  
    modified_lines = []
    for line in lines:
        if line.startswith('tg_token = '):
            modified_lines.append(f"tg_token = '{tg_token}'\n")
        elif line.startswith('tg_channel = '):
            modified_lines.append(f"tg_channel = '{tg_channel}'\n")
        else:
            modified_lines.append(line)
    
    with open('config.py', 'w') as file:
        file.writelines(modified_lines)
    
    print('Telegram credentials updated successfully.')


def get_position_data(action,symbol):
    pos_price, identifier, volume = 0.0, 1, 0.0
    positions=mt5.positions_get(symbol=symbol)
    # print(positions)
    if positions == None:
        print(f'No positions on {symbol}')
    elif len(positions) > 0:
        # print(f'Total positions on {symbol} =',len(positions))
        for position in positions:
            post_dict = position._asdict()
            comment = post_dict['comment']
            if comment == 'SELL' if action == 'BUY' else 'BUY':
                pos_price = post_dict['price_open']
                identifier = post_dict['identifier']
                volume = post_dict['volume']

    return pos_price,identifier,volume


def close_positions_by_symbol(action,symbol):
    volume = 0.0
    try:
        pos_price, identifier, volume = 0.0, 1, 0.0
        positions=mt5.positions_get(symbol=symbol)
        print(positions)
        if positions == None:
            print(f'No positions on {symbol}')
        elif len(positions) > 0:
            print(f'Total positions on {symbol} =',len(positions))
            for position in positions:
                post_dict = position._asdict()
                comment = post_dict['comment']
                pos_price = post_dict['price_open']
                identifier = post_dict['identifier']
                volume = post_dict['volume']
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL  ,
                    "position":identifier,
                    "price": pos_price,
                    "comment": "Position Closed",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_FOK,
                }
                
                if comment == 'SELL' and action == 'BUY':
                    result = mt5.order_send(request)
                    volume  = result._asdict()['volume']
                    print(result)

                if comment == 'BUY' and action == 'SELL':
                    result = mt5.order_send(request)
                    volume  = result._asdict()['volume']
                    print(result)

    except Exception as e:
        print(e)
    return volume
def close_order(action,symbol,volume,identifier,price):
    request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL  ,
                "position":identifier,
                "price": price,
                "comment": "Position Closed",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
    result = mt5.order_send(request)
    print(result)

def place_buy_order(action,symbol,volume,price):
    request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "comment": "BUY",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
    result = mt5.order_send(request)
    # print(result)

def place_sell_order(action,symbol,volume,price):
    request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "comment": "SELL",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
    # result = mt5.order_send(request)

def place_order(action,symbol,volume,price,tp,sl):

    if tp != 0 and sl != 0:
        sl = price * (1 - (float(sl)/100)) if action == 'BUY' else price * (1 + (float(sl)/100))
        tp = price * (1 + (float(tp)/100)) if action == 'BUY' else price * (1 - (float(tp)/100))

    request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": None if sl == 0 else sl,
                "tp": None if tp == 0 else tp,
                "comment": 'BUY' if action == "BUY" else 'SELL',
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
    result = mt5.order_send(request)
    volume  = result._asdict()['volume']
    print(result)
    return volume

#########################################################################
#########################################################################
#######################   ROUTES.PY  ####################################
#########################################################################
#########################################################################
#########################################################################


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''

    if request.method == 'POST':
        if request.form.get('username') != config.admin_username or \
                request.form.get('password') != config.admin_password:
            error = 'Invalid Credentials. Please try again.'
            flash(format('Invalid credentials. Please try again.'), 'error')
        else:
            #auth_data = request.form.to_dict(flat=True)
            write('auth.txt', 'authenticated')
            write('ip_address.txt', ip_address())
            return redirect(url_for('index'))
    return render_template('login.html', error=error)

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    write('auth.txt', 'unauthenticated')
    write('ip_address.txt', '')
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def main():
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()
    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('index'))

@app.route('/password_reset',methods=['POST'])
def reset_password():
    if request.method == 'POST':
        admin_username = request.form.get('current_username')
        old_pass = request.form.get('current_password')
        new_pass = request.form.get('new_password')
        if admin_username == config.admin_username:
            if old_pass == config.admin_password:
                config.admin_password = new_pass
                with open('config.py', 'r') as f:
                    config_contents = f.read()
                new_config_contents = config_contents.replace(
                    f"admin_password = '{old_pass}'", f"admin_password = '{new_pass}'")
                with open('config.py', 'w') as f:
                    f.write(new_config_contents)
                    flash(format('Admin Password Changed Successfuly'), 'success')

            else:
                flash(format('Current Admin Password Is Not Valid'), 'error')
        else:
            flash(format('Admin Username Is Not Valid'), 'error')
    return redirect(url_for('change_password'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():        
    pass
    return render_template('change_password.html')



@app.route('/dashboard', methods=['GET', 'POST'])
async def index():
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        script_type = request.form.get('script_type',"")
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
            syntax =    '{</br>"symbol": ' + '"' + symbol + '",\
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
async def signals():
  auth_session = read('auth.txt')
  ip_session = str(read('ip_address.txt'))
  ip_add = ip_address()
    
  if auth_session != 'authenticated' or ip_session != ip_add:
    return redirect(url_for('login'))
  with open('signals.json', 'r') as f:
    trade_data = json.load(f)
    df = pd.DataFrame(
      trade_data,
      columns=['order_time', 'symbol', 'action', 'entry', 'qty', 'qty_type'])
    df.rename(columns={
      'order_time': 'TIME',
      'symbol': 'SYMBOL',
      'action': 'SIDE',
      'qty': 'QTY',
      'entry': 'ENTRY',
      # 'tp': 'TP',
      # 'sl': 'SL',
      'qty_type': 'ACCOUNT'
    },
              inplace=True)
    df = df.sort_values(by="TIME", ascending=False)
    #print(df)

  return render_template('signals.html',
                         tables=[df.to_html(classes='data')],
                         titles=df.columns.values)


@app.route('/trades', methods=['GET', 'POST'])
async def trades():
  auth_session = read('auth.txt')
  ip_session = str(read('ip_address.txt'))
  ip_add = ip_address()

  if auth_session != 'authenticated' or ip_session != ip_add:
    return redirect(url_for('login'))
  with open('trades.json', 'r') as f:
    trade_data = json.load(f)
    df = pd.DataFrame(
      trade_data,
      columns=['order_time', 'order_id', 'symbol', 'action', 'price', 'qty'])
    df.rename(columns={
      'order_time': 'TIME',
      'order_id': 'ORDER ID',
      'symbol': 'SYMBOL',
      'action': 'SIDE',
      'qty': 'QTY',
      'price': 'PRICE'
    },
              inplace=True)
    df = df.sort_values(by="TIME", ascending=False)
    #print(df)

  return render_template('trades.html',
                         tables=[df.to_html(classes='data')],
                         titles=df.columns.values)

@app.route('/max_loss_settings', methods=['GET', 'POST'])
def max_loss_settings():
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
      write('max_loss_value.txt',max_loss_value)
    if max_loss_value == '':
      max_loss_value = 0
    return render_template('settings.html',max_loss_value=max_loss_value)

  return render_template('settings.html',max_loss_value=max_loss_value)

@app.route('/reset_max_loss', methods=['GET', 'POST'])
def reset_max_loss():
  auth_session = read('auth.txt')
  ip_session = str(read('ip_address.txt'))
  ip_add = ip_address()

  if auth_session != 'authenticated' or ip_session != ip_add:
    return redirect(url_for('login'))
  if request.method == 'POST':
    write('max_loss.txt','')

    return redirect(url_for('max_loss_settings'))

def get_display_data(value, default='NO'):
    if len(value) > 0:
        return value[:len(value) - 5] + '************'
    else:
        return default

@app.route('/api_settings', methods=['GET', 'POST'])
def api_settings():
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    importlib.reload(config)

    login = config.login
    half_lenght = int((len(str(config.password))/2)*1.25)
    password = config.password[:len(str(config.password))-half_lenght] + '************'
    server = config.server

    return render_template('add_api.html',login=login,password=password,server=server)


def process_value(value, account_number):
    if len(str(value)) > 0:
        return value[:len(str(value))-5] + '************'
    else:
        return f'NO_VALUE_FOUND_{account_number}'



@app.route('/add_metaapi_<int:account_number>', methods=['GET', 'POST'])
def add_metaapi(account_number):
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    importlib.reload(config)
    
    token_key = f'token_{account_number}'
    account_id_key = f'account_id_{account_number}'
    
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        server = request.form.get('server')
        
        if len(login) > 0 and len(password) > 0 and len(server) > 0:
            update_config('login = ', login, 'password = ', password, 'server = ', server)
            # importlib.reload(login)
    return redirect(url_for('api_settings'))

@app.route('/add_api_telegram_<int:account_number>', methods=['GET', 'POST'])
def add_api_telegram(account_number):
    auth_session = read('auth.txt')
    ip_session = str(read('ip_address.txt'))
    ip_add = ip_address()

    if auth_session != 'authenticated' or ip_session != ip_add:
        return redirect(url_for('login'))
    importlib.reload(config)
    
    tg_token_key = f'tg_token_{account_number}'
    tg_channel_key = f'tg_channel_{account_number}'
    
    if request.method == 'POST':
        tg_token = request.form.get('tg_token')
        tg_channel = request.form.get('tg_channel')
        
        if len(tg_token) > 0 and len(tg_channel) > 0:
            update_config(f'{tg_token_key} = ', tg_token, f'{tg_channel_key} = ', tg_channel)
            
    return redirect(url_for('api_settings'))


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=80, debug=True, threaded=True)
