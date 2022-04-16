import re
import requests
import json
import time
from tronpy import Tron
from etherscan import Etherscan
from time import sleep
import traceback
from config import my_addresses, reddit, ftxus_client, etherscan_key

def parse_initial(string, user, comment_id):
    h_amount = re.findall('(?<=\[H\]\s)(?:\d+)?\.?\d+(?=\s)', string)[0]
    h_coin = re.findall('(?:\[H\]\s[\d.]+\s)(\w+)', string)[0]
    w_coin = re.findall('(?:\[W\]\s)(\w+)', string)[0]
    receiving_net = re.findall('(?i)(?:!RECEIVE TO NETWORK:\s)(\S+)', string)[0].upper()
    receiving_addr = re.findall('(?i)(?:!RECEIVE TO ADDRESS:\s)(\S+)', string)[0]
    sending_net = re.findall('(?i)(?:!SENDING FROM NETWORK:\s)(\S+)', string)[0].upper()
    sending_addr = re.findall('(?i)(?:!SENDING FROM ADDRESS:\s)(\S+)', string)[0]

    transaction_info = {'have_amount':h_amount,'have_coin':h_coin,'want_coin':w_coin,
                        'receiving_network':receiving_net,'receiving_address':receiving_addr,
                        'sending_network':sending_net, 'sending_address':sending_addr, 'user':user.name,
                        'comment_id':comment_id}
    return transaction_info

my_withdrawal_fees = {'ETH':{'ERC-20':.005, 'BSC':.00035},
                           'BTC':{'BTC':.0003, 'SOL':.00002, 'BSC':.00002},
                           'USDT':{'ERC-20':15, 'BSC':1, 'TRC-20':1,'SOL':1},
                           'LTC':{'LTC':.01},
                           'SOL':{'SOL':.01},
                           'DOGE':{'DOGE':1},
                           'TRX':{'TRC-20':10},
                           'LINK':{'ERC-20':1, 'SOL':.08}}

def survey_responses(submission_id, reddit, done, my_addresses):
    new_records = []
    for comment in reddit.submission(submission_id).comments:
        id = comment.id
        if comment.id not in done:
            done.append(id)
            if reddit.comment(id).body.upper() == '[DELETED]':
                continue
            try:
                comment_string = reddit.comment(id).body.replace('\\','')
                if not check_format(comment_string):
                    send_format_error_response(id, reddit, 'https://google.com')
                    continue
                user = reddit.comment(id).author
                transaction_info = parse_initial(comment_string, user, id)
                print(transaction_info)
                unsupported, transaction_info = check_supported(transaction_info,'https://google.com')
                if unsupported:
                    send_unsupported_response(unsupported, id, reddit)
                    continue
                quoted_price, quoted_w_amount, receiving_net, network_fee, inverse_quote = get_quote(transaction_info['have_coin'], transaction_info['have_amount'], transaction_info['want_coin'], transaction_info['receiving_network'], my_withdrawal_fees)
                my_address = my_addresses[transaction_info['have_coin']][transaction_info['sending_network']]
                my_address_url = get_url(my_address, transaction_info['sending_network'])
                sending_address_url = get_url(transaction_info['sending_address'], transaction_info['sending_network'])
                receiving_address_url = get_url(transaction_info['receiving_address'], receiving_net)
                send_response(reddit,transaction_info,quoted_price, quoted_w_amount,network_fee,inverse_quote,id, my_address, my_address_url, sending_address_url, receiving_address_url)
                new_records.append(transaction_info)
            except Exception as e:
                print(traceback.format_exc())
                print(e)
    return new_records, done

grammar = {('BTC', 'YFI', 'USDT', 'UNI', 'TRX', 'SUSHI', 'SOL', 'SHIB', 'MKR', 'MATIC', 'LTC', 'LINK', 'GRT', 'DOGE', 'BAT', 'BCH', 'AAVE', 'TUSD', 'USDC', 'BUSD'):'a',
           ('AVAX', 'ETH', 'HUSD'):'an'}

usd_equivs = ['TUSD', 'USDC', 'BUSD', 'HUSD']



supported_withdrawal_networks = {'ETH':['ERC-20', 'SOL', 'BSC'],
                                 'LTC':['LTC'],
                                 'TRX':['TRC-20']}

chain_explorers = {'TRC-20':'https://tronscan.org/#/address/',
                   'ERC-20':'https://etherscan.io/address/',
                   'BTC':'https://www.blockchain.com/btc/address/',
                   'BSC':'https://bscscan.com/address/',
                   'SOL':'https://explorer.solana.com/address/',
                   'DOGE':'https://dogechain.info/address/',
                   'LTC':'https://blockchair.com/litecoin/transaction/'}
def get_url(address, chain):
    return chain_explorers[chain] + address


def send_response(reddit, transaction_info, quoted_price, quoted_w_amount, network_fee, inverse_quote, comment_id, my_address, my_address_url, sending_address_url, receiving_address_url):
    comment = reddit.comment(id=comment_id)
    for key in grammar.keys():
        if transaction_info['have_coin'] in key:
            article = grammar[key]
            break
    quote_string = '''___
## Quote:

* Estimated rate: **{} {}** per **{}** (**{} {}** = **1 {}**)
* If we receive **{} {}**, you will receive back approximately **{} {}**
* Formula `= (rate * base amount) - chain fee = ({} * {}) - {} =` **{} {}**

___'''\
        .format(quoted_price, transaction_info['want_coin'], transaction_info['have_coin'], inverse_quote, transaction_info['have_coin'], transaction_info['want_coin'], transaction_info['have_amount'], transaction_info['have_coin'], quoted_w_amount,
                transaction_info['want_coin'], quoted_price, transaction_info['have_amount'], network_fee, quoted_w_amount, transaction_info['want_coin'])
    transaction_string = '''
## Transaction:

Please check the following information for accuracy:

* You are requesting to receive **{}** on the **{}** chain at deposit address *[{}]({})*
* In exchange for the **{}**, you intend to send **{}** on the **{}** chain, and the **{}** will be sent from address *[{}]({})*

If any of the above information is incorrect, **DO NOT** initiate the {} transaction. You may reset your exchange request with the correct information by starting over with a new top-level comment on the thread.

**If all of the information is correct, you may proceed by sending the {} on the {} chain to the address: [{}]({})**

*Once {} {} deposit (of any amount) is received from your [sending address]({}), the full amount will be converted to {} and sent to your [deposit address]({}). Please note that the actual exchange rate may be slightly lower or higher than the estimate, subject to market volatility.*

___

^(For questions and concerns, please contact) u/CryptoOTC_creator'''.format(transaction_info['want_coin'], transaction_info['receiving_network'], transaction_info['receiving_address'], receiving_address_url,
                                                                            transaction_info['want_coin'], transaction_info['have_coin'], transaction_info['sending_network'],
                                                                            transaction_info['have_coin'], transaction_info['sending_address'], sending_address_url, transaction_info['have_coin'],
                                                                            transaction_info['have_coin'], transaction_info['sending_network'], my_address, my_address_url, article, transaction_info['have_coin'],
                                                                            sending_address_url, transaction_info['want_coin'], receiving_address_url)





    comment.reply(quote_string+transaction_string)




coins = {'BTC':{'base':['USDT','USD'], 'quote':['ETH','DOGE','MATIC', 'SOL']},
         'ETH':{'base':['BTC','USD', 'USDT'], 'quote':[]},
         'USDT':{'base':['USD'], 'quote':['BTC', 'DOGE', 'SOL', 'ETH', 'TRX']},
         'MATIC':{'base':['BTC', 'USD'], 'quote':[]},
         'DOGE':{'base':['BTC', 'USDT', 'USD'], 'quote':[]},
         'SOL':{'base':['BTC', 'USDT', 'USD'], 'quote':[]},
         'TRX':{'base':['USDT', 'USD'], 'quote':[]},
         'LTC':{'base':['BTC', 'USDT', 'USD'], 'quote':[]},
         'USD':{'base':[], 'quote':['BTC', 'AVAX', 'YFI', 'USDT', 'UNI', 'TRX', 'SUSHI', 'SOL', 'SHIB', 'MKR', 'MATIC', 'LTC', 'LINK', 'GRT', 'ETH', 'DOGE', 'BAT', 'AAVE']}}



def get_quote(h_coin, h_amount, w_coin, receiving_net, my_withdrawal_fees):
    fee = my_withdrawal_fees[w_coin][receiving_net]
    if h_coin != w_coin:
        spread = .026
        base_endpoint = 'https://ftx.us/api/markets/'
        sig_fix_re = '\d+(?:\.0*[1-9][1-9]?)?'
        h_amount = float(h_amount)
        if h_coin in usd_equivs:
            h_coin = 'USD'
        if w_coin in usd_equivs:
            w_coin = 'USD'
        if h_coin in coins[w_coin]['base'] or h_coin in coins[w_coin]['quote']:
            if h_coin in coins[w_coin]['base']:
                market = w_coin + '/' + h_coin
                base = True
            elif h_coin in coins[w_coin]['quote']:
                base = False
                market = h_coin + '/' + w_coin
            url = base_endpoint+market
            response = json.loads(requests.get(url).content)['result']
            try:
                if not base:
                    best_price = response['ask']
                    quoted_price = best_price * (1-spread)
                    quoted_w_amount = (h_amount * quoted_price) - fee
                else:
                    best_price = response['bid']
                    quoted_price = 1 / (best_price * (1+spread))
                    quoted_w_amount = (h_amount * quoted_price) - fee
                inverse_quote = re.findall(sig_fix_re, str('{:f}'.format(1/quoted_price)))[0]
                quoted_price = re.findall(sig_fix_re, str('{:f}'.format(quoted_price)))[0]
                quoted_w_amount = re.findall(sig_fix_re, str(quoted_w_amount))[0]

                print(quoted_w_amount, quoted_price, fee, inverse_quote)
            except Exception as e:
                print(e)
                pass
        else:
            h_url = base_endpoint + h_coin + '/' + 'usd'
            h_price = json.loads(requests.get(h_url).content)['result']['bid']
            w_url = base_endpoint + w_coin + '/' + 'usd'
            w_price = json.loads(requests.get(w_url).content)['result']['ask']
            quoted_price = (h_price / w_price) * (1-(spread*1.5))
            quoted_w_amount = (h_amount * quoted_price) - fee
            inverse_quote = re.findall(sig_fix_re, str('{:f}'.format(1 / quoted_price)))[0]
            quoted_price = re.findall(sig_fix_re, str('{:f}'.format(quoted_price)))[0]
            quoted_w_amount = re.findall(sig_fix_re, str('{:f}'.format(quoted_w_amount)))[0]
    else:
        quoted_price = 1
        quoted_w_amount = float(h_amount) - fee
        inverse_quote = 1
    return quoted_price, quoted_w_amount, receiving_net, fee, inverse_quote




def find_sender(chain, txid, tag=None, etherscan_key=etherscan_key):
    if chain == 'trx':
        client = Tron()
        sender = client.get_transaction(txid)['raw_data']['contract'][0]['parameter']['value']['owner_address']
        return sender
    elif chain == 'erc20':
        client = Etherscan(etherscan_key)
        sender = client.get_proxy_transaction_receipt(txhash=txid)['from']
        return sender
    elif chain == 'btc':
        sender = None
    elif chain == 'sol':
        base_url = 'https://public-api.solscan.io/transaction/'
        full_url = base_url+txid
        sender = json.loads(requests.get(full_url).content)['signer'][0]
    else:
        sender = None
    return sender


def fetch_new_deposits(seconds_back, archived_ids):
    new_records = []
    new_ids = []
    ms_back = seconds_back * 1000
    since_time = (time.time()*1000) - ms_back
    deposit_records = ftxus_client.fetch_deposits(since=since_time)
    for record in deposit_records:
        if record['info']['status'] != 'confirmed' or record['info']['id'] in archived_ids:
            continue
        transaction_id = record['info']['id']
        coin = record['info']['coin']
        size = record['info']['size']
        txid = record['info']['txid']
        method = record['info']['method']
        print(method)
        #need to call a function that takes in txid and outputs sender address
        sender_address = find_sender(method, txid)
        print(sender_address)
        new_records.append({'id':transaction_id, 'coin':coin,'size':size, 'txid':txid, 'sender_address':sender_address, 'method':method})
        new_ids.append(transaction_id)
    return new_records, new_ids





def exchange(from_c, to_c, amount_f, client):
    #if amount is smaller than $25 usd, find a quote on my own and make my send amount based on the quote (will have dust in every coin to compensate)
    #markets = coins[from_c]
    fixed_spread = .025
    if from_c in usd_equivs:
        from_c = 'USD'
    if to_c in usd_equivs:
        to_c = 'USD'
    if to_c in coins[from_c]['base']:
        base = True
        market = from_c + '/' + to_c
        trade_id = client.create_market_sell_order(market, float(amount_f)*(1-fixed_spread))['info']['id']
        sleep(2)
        if client.fetch_order(id=trade_id)['info']['status'] == 'closed':
            trade_info = client.fetch_order(id=trade_id)
            to_amount = trade_info['cost']
            avg_fill = (trade_info['info']['avgFillPrice']) * (1-fixed_spread)
        else:
            to_amount = None
    elif to_c in coins[from_c]['quote']:
        base = False
        market = to_c + '/' + from_c
        ask = client.fetch_ticker(market)['ask']
        order_size = float(amount_f) / ask
        trade_id = client.create_market_buy_order(market, order_size*(1-fixed_spread))['info']['id']
        sleep(2)
        if client.fetch_order(id=trade_id)['info']['status'] == 'closed':
            trade_info = client.fetch_order(id=trade_id)
            to_amount = trade_info['info']['size']
            avg_fill = (1 / float(trade_info['info']['avgFillPrice'])) * (1-fixed_spread)
        else:
            to_amount = None
    else:
        #exchange h coin for usd
        inter_market = from_c + '/' + 'USD'
        #bid = client.fetch_ticker(market)['bid']
        inter_id = client.create_market_sell_order(inter_market, float(amount_f*(1-fixed_spread)))['info']['id']
        sleep(2)
        inter_info = client.fetch_order(id=inter_id)
        inter_amount = inter_info['cost']
        inter_fill = inter_info['info']['avgFillPrice']
        #exchange usd for w coin
        market = to_c + '/' + 'USD'
        ask = client.fetch_ticker(market)['ask']
        order_size = float(inter_amount) / ask
        trade_id = client.create_market_buy_order(market, order_size)['info']['id']
        sleep(2)
        trade_info = client.fetch_order(id=trade_id)
        to_amount = trade_info['info']['size']
        avg_fill =  (float(inter_fill) / float(trade_info['info']['avgFillPrice'])) * (1-fixed_spread)
    theoretical_amount = (float(avg_fill)*float(amount_f))
    usd_price = json.loads(requests.get('https://ftx.us/api/markets/'+to_c+'/'+'USD').content)['result']['price']
    if theoretical_amount * usd_price < 25:
        theoretical_amount = None
    return float(to_amount), theoretical_amount



#exchange('USDT', 'BTC', 8, ftxus_client)





def withdraw(coin, amount, to_address, chain, client, ftx_fees, my_fees,method_conversion):
    ftx_fee = ftx_fees[coin][chain]
    my_fee = my_fees[coin][chain]
    net_fee = my_fee - ftx_fee
    net_send = amount - net_fee
    ftx_sendchain = method_conversion[chain]
    response = client.withdraw(coin, net_send, to_address, {'network':ftx_sendchain})
    print(response)
    return response['id'], my_fee

def send_final_confirmation(transaction, txid, txid_url, reddit):
    comment = reddit.comment(id=transaction['comment_id'])
    sig_fig_re = '\d+(?:\.0*[1-9][1-9]?)?'
    transaction['actual_deposit'] = re.findall(sig_fig_re, str('{:f}'.format(float(transaction['actual_deposit']))))[0]
    transaction['net_send'] = re.findall(sig_fig_re, str('{:f}'.format(float(transaction['net_send']))))[0]
    transaction['to_c_amount'] = re.findall(sig_fig_re, str('{:f}'.format(float(transaction['to_c_amount']))))[0]
    #quoted_price = re.findall(sig_fix_re, str('{:f}'.format(quoted_price)))[0]

    string = '''u/{},

A deposit of **{} {}** was received from your [sending address]({}); **{} {}** has been sent to your [receiving address]({})!

The transaction can be tracked with the txid: [***{}***]({})

The **{} {}** was converted for **{} {}** and an outgoing transaction fee of **{} {}** was deducted.

*You may reply to this comment to confirm completion of the transaction with the command:*

`!Confirm`

^(If an error has been made with this transaction, please contact) u/CryptoOTC_creator ^(for manual review.)'''.format(transaction['user'], transaction['actual_deposit'], transaction['have_coin'], transaction['sending_address'], transaction['net_send'], transaction['want_coin'],
                                                                                                                                   transaction['receiving_address'], txid, txid_url, transaction['actual_deposit'], transaction['have_coin'], transaction['to_c_amount'], transaction['want_coin'],
                                                                                                                                   transaction['my_fee'], transaction['want_coin'])
    comment.reply(string)



def check_format(string):
    #if pass, move on | if not pass, instruct help
    expected = '\[H\]\s?[\d.]+\s[\w\d]+\s?\[W\]\s?[\w\d]+\s*!(?i)RECEIVE TO NETWORK:\s?\S+\s*!RECEIVE TO ADD?RR?ESS?:\s?\S+\s*!SENDING FROM NETWORK:\s?\S+\s*!SENDING FROM ADD?RR?ESS?:\s?\S+(?:$|[\s\t\n])'
    if re.search(expected, string):
        return True
    else:
        return False

def send_format_error_response(id, reddit, reference_url):
    comment = reddit.comment(id=id)
    comment.reply('''*Your request does not match the expected format. You may post a new top-level comment and your request will be reset.*

You may refer to [this sample]({}) for the proper formatting.

___
^(For questions and concerns, please contact) u/CryptoOTC_creator'''.format(reference_url))

def check_supported(transaction_info, supported_url):
    unsupported = []
    actual_h, actual_w, actual_s, actual_r = None, None, None, None
    raw_h = transaction_info['have_coin'].lower()
    raw_w = transaction_info['want_coin'].lower()
    raw_snet = transaction_info['sending_network'].lower()
    raw_rnet = transaction_info['receiving_network'].lower()
    for key in list(coin_equivalance.keys()):
        if raw_h in key:
            actual_h = coin_equivalance[key]
        if raw_w in key:
            actual_w = coin_equivalance[key]
    if not actual_h:
        unsupported.append('*Sending coin:* **{}** *unsupported or unrecognized. Check [here]({}) for list of supported coins*'.format(transaction_info['have_coin'], supported_url))
    if not actual_w:
        unsupported.append('*Receiving coin:* **{}** *unsupported or unrecognized. Check [here]({}) for list of supported coins*'.format(transaction_info['want_coin'], supported_url))
    for key in list(chain_equivalence.keys()):
        if raw_snet in key:
            print('426', raw_snet)
            inter_s = chain_equivalence[key]
            try:
                print(supported_withdrawal_networks)
                print(actual_h)
                actual_ss = supported_withdrawal_networks[actual_h]
                print(actual_ss)
                if inter_s in actual_ss:
                    actual_s = inter_s
            except Exception as e:
                print('434')
                print(e)
                pass
        if raw_rnet in key:
            inter_r = chain_equivalence[key]
            try:
                actual_rs = supported_withdrawal_networks[actual_w]
                if inter_r in actual_rs:
                    actual_r = inter_r
            except:
                pass
    if not actual_s:
        unsupported.append('*Sending network:* **{}** *unsupported or unrecognized. Check [here]({}) for list of supported networks*'.format(transaction_info['sending_network'], supported_url))
    if not actual_r:
        unsupported.append('*Receiving network:* **{}** *unsupported or unrecognized. Check [here]({}) for list of supported networks*'.format(transaction_info['receiving_network'], supported_url))
    transaction_info['have_coin'] = actual_h
    transaction_info['want_coin'] = actual_w
    transaction_info['sending_network'] = actual_s
    transaction_info['receiving_network'] = actual_r
    return unsupported, transaction_info


def send_unsupported_response(unsupported, id, reddit):
    string = ''
    for i, item in enumerate(unsupported):
        if i >= 1:
            string += '\n\n'
        string += item
    string += '''\n___
^(For questions and concerns, please contact) u/CryptoOTC_creator'''
    comment = reddit.comment(id=id)
    comment.reply(string)





chain_equivalence = {('erc-20', 'erc20', 'eth', 'erc', 'ethereum', 'ether'):'ERC-20',
                     ('trc-20', 'trc20', 'tron', 'trc', 'trx', 'tronix', 'TRC-20'):'TRC-20',
                     ('sol', 'spl', 'solana'):'SOL',
                     ('bsc', 'binancesmartchain', 'binance smart chain', 'bep20', 'bep-20'):'BSC',
                     }

coin_equivalance = {('ethereum', 'eth', 'ether'):'ETH',
                    ('ltc', 'litecoin'):'LTC',
                    ('trx', 'trc', 'tron'):'TRX'}









