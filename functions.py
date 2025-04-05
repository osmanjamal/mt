from flask import Flask, request, render_template, redirect, url_for,flash
import json
from main import mt5
import datetime

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


def close_positions_by_symbol(action,symbol,output):
    volume = 0.0
    try:
        pos_price, identifier, volume = 0.0, 1, 0.0
        positions=mt5.positions_get(symbol=symbol)
        output.append(positions)
        if positions == None:
            output.append(f'No positions on {symbol}')
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
                    output.append(result)

                if comment == 'BUY' and action == 'SELL':
                    result = mt5.order_send(request)
                    volume  = result._asdict()['volume']
                    output.append(result)

    except Exception as e:
        output.append(e)
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

def place_order(action,symbol,volume,price,output):
    request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "comment": 'BUY' if action == "BUY" else 'SELL',
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
    result = mt5.order_send(request)
    volume  = result._asdict()['volume']
    output.append(result)
    return volume


class TradingActions:
    def __init__(self, action, symbol, qty, price, tp, sl, which_account, output):
        self.action = action
        self.symbol = symbol
        self.qty = qty
        self.price = price
        self.tp = tp
        self.sl = sl
        self.which_account = which_account
        self.output = output if output else []

    def close_positions(self):
        try:
            order_response = close_positions_by_symbol(self.action, self.symbol, self.output)
        except Exception as e:
            print(e)

    def place_order(self):
        try:
            order_response = place_order(self.action, self.symbol, abs(self.qty), self.price, self.output)
        except Exception as e:
            print(e)

    def execute_action(self, market_position):
        if self.action == "BUY":
            self.close_positions()
            if market_position == "long":
                self.place_order()
        elif self.action == "SELL":
            self.close_positions()
            if market_position == "short":
                self.place_order()

    def write_order_details(self):
        self.output.append("--------------------------------------------------------------")
        self.output.append("------------------   ORDER DETAILS   -------------------------")
        self.output.append("--------------------------------------------------------------")
        try:
            dt = datetime.datetime.now()
            order_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            if self.order_response:
                write_signal_data(order_time, self.action, self.symbol, self.price, self.tp, self.sl, self.qty, self.which_account)
                self.output.append(
                    f"| Order Placed Time : {order_time} \n| Side : {self.action} \n| Symbol : {self.symbol} \n| Entry : {self.price} \n| TP : {self.tp} \
                \n| SL : {self.sl} \n| Qty : {self.qty} \n| In Account : {self.which_account}"
                )
        except Exception as e:
            self.output.append("No Order Placed")
            self.output.append(e)
        self.output.append("-------------------------------------------------------------")
        self.output.append("-------------------  END OF REQUEST  ------------------------")
        self.output.append("-------------------------------------------------------------")
        with open("output.txt", "a", encoding="utf-8") as output_file:
            for line in reversed(self.output):
                output_file.write(line + "\n")                
