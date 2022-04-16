from function_lib import parse_initial, get_quote, find_sender, fetch_new_deposits, exchange, withdraw, survey_responses, send_final_confirmation
from time import sleep
import pickle
from config import reddit, my_addresses, ftxus_client


chain_explorers_txid = {'TRC-20':'https://tronscan.org/#/transaction/',
                   'ERC-20':'https://etherscan.io/tx/',
                   'BTC':'https://www.blockchain.com/btc/tx/',
                   'BSC':'https://bscscan.com/tx/',
                   'SOL':'https://explorer.solana.com/tx/',
                   'DOGE':'https://dogechain.info/tx/'}
chain_explorers = {'TRC-20':'https://tronscan.org/#/address/',
                   'ERC-20':'https://etherscan.io/address/',
                   'BTC':'https://www.blockchain.com/btc/address/',
                   'BSC':'https://bscscan.com/address/',
                   'SOL':'https://explorer.solana.com/address/',
                   'DOGE':'https://dogechain.info/address/'}

method_conversion = {'TRC-20':'trx', 'ERC-20':'erc20','OMNI':'omni', 'BEP2':'bep2', 'BSC':'BSC', 'MATIC':'matic', 'SOL':'sol', 'LTC':'ltc'}

ftx_withdrawal_fees = {'ETH':{'ERC-20':.0005, 'BSC':0},
                           'BTC':{'BTC':0, 'SOL':0, 'BSC':0},
                           'USDT':{'ERC-20':2.5, 'BSC':0, 'TRC-20':0, 'SOL':0},
                           'LTC':{'LTC':0},
                           'SOL':{'SOL':0},
                           'DOGE':{'DOGE':0},
                           'TRX':{'TRC-20':0},
                           'LINK':{'ERC-20':.25, 'SOL':0},
                      'TUSD':{'ERC-20':2.5},
                      'USDC':{'ERC-20':2.5, 'SOL':0, 'BSC':0},
                      'BUSD':{'ERC-20':2.5, 'BSC':0},
                      'HUSD':{'ERC-20':2.5}}


my_withdrawal_fees = {'ETH':{'ERC-20':.005, 'BSC':.00035},
                           'BTC':{'BTC':.0003, 'SOL':.00002, 'BSC':.00002},
                           'USDT':{'ERC-20':15, 'BSC':1, 'TRC-20':1,'SOL':1},
                           'LTC':{'LTC':.01},
                           'SOL':{'SOL':.01},
                           'DOGE':{'DOGE':1},
                           'TRX':{'TRC-20':10},
                           'LINK':{'ERC-20':1, 'SOL':.08},
                      'TUSD':{'ERC-20':15},
                      'USDC':{'ERC-20':15, 'SOL':1, 'BSC':1},
                      'BUSD':{'ERC-20':15, 'BSC':1},
                      'HUSD':{'ERC-20':15}}


done = []
open_transactions = []
archived_deposit_ids = []
deposit_records = []
pending_withdrawals = {}
first = True
while True:

    #collect all new responses
    new_records, done = survey_responses('tda2mo', reddit, done, my_addresses)
    open_transactions.extend(new_records)

    #get new deposits
    if first:
        seconds_back = 40000
        archived_deposit_ids = pickle.load(open('archived_deposits.p', 'rb'))['ids']
        first = False
    else:
        seconds_back = 40000
    deposit_records, new_ids = fetch_new_deposits(seconds_back, archived_deposit_ids)
    archived_deposit_ids.extend(new_ids)
    if new_ids:
        pickle.dump({'ids': archived_deposit_ids}, open("archived_deposits.p", "wb"))
    print(open_transactions)
    print(deposit_records)
    for transaction in open_transactions:
        for deposit in deposit_records:
            ftx_method_format = method_conversion[transaction['sending_network']]

            if deposit['sender_address'] == transaction['sending_address'] and deposit['coin'] == transaction['have_coin'] and deposit['method'] == ftx_method_format:
                if transaction['have_coin'] != transaction['want_coin']:
                    to_c_amount, theoretical = exchange(transaction['have_coin'], transaction['want_coin'], deposit['size'], ftxus_client)
                    if theoretical:
                        to_c_amount = theoretical
                else:
                    to_c_amount = float(deposit['size'])
                transaction['actual_deposit'] = deposit['size']
                transaction['to_c_amount'] = to_c_amount
                withdrawal_id, my_fee = withdraw(transaction['want_coin'],to_c_amount,transaction['receiving_address'],transaction['receiving_network'], ftxus_client,ftx_withdrawal_fees,my_withdrawal_fees, method_conversion)
                transaction['my_fee'] = my_fee
                transaction['net_send'] = to_c_amount - my_fee
                pending_withdrawals[withdrawal_id] = transaction



                #execute the exchange
                #execute the withdrawal
                #add withdrawal to pending txid confirmation list
    all_withdrawals = ftxus_client.fetch_withdrawals(limit=None)
    for pending in list(pending_withdrawals.keys()):
        for withdrawal in all_withdrawals:
            if withdrawal['id'] == pending and withdrawal['txid']:
                txid = withdrawal['txid']
                transaction = pending_withdrawals[pending]
                txid_url = chain_explorers_txid[transaction['receiving_network']] + txid
                send_final_confirmation(transaction,txid,txid_url,reddit)
                del pending_withdrawals[pending]
    sleep(30)



