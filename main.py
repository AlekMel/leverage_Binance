import ccxt
import PySimpleGUI as sg
import logging
import concurrent.futures
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройка темы в стиле MS-DOS
sg.theme('DarkBlue3')

# Инициализация биржи Binance (будет обновлено после ввода ключей)
exchange = None

def initialize_exchange(api_key, api_secret):
    global exchange
    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        exchange.load_markets()
        logger.info("Биржа Binance инициализирована успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации биржи: {str(e)}")
        return False

def get_perpetual_futures_list():
    logger.info("Получение списка бессрочных фьючерсов (swap)")
    try:
        markets = exchange.load_markets()
        perpetual_futures = [symbol for symbol, market in markets.items() 
                             if market['type'] == 'swap' and market['linear']]
        logger.info(f"Получено {len(perpetual_futures)} бессрочных фьючерсов (swap)")
        return perpetual_futures
    except Exception as e:
        logger.error(f"Ошибка при получении списка фьючерсов: {str(e)}")
        return []

def get_leverage(symbol):
    logger.info(f"Проверка плеча для {symbol}")
    try:
        # Удаляем лишние части из символа
        clean_symbol = symbol.split(' ')[0].replace('/', '').replace(':USDC', '').replace(':USDT', '')
        position_info = exchange.fapiPrivateV2GetPositionRisk({'symbol': clean_symbol})
        for position in position_info:
            if position['symbol'] == clean_symbol:
                leverage = float(position['leverage'])
                logger.info(f"Текущее плечо для {clean_symbol}: {leverage}")
                return leverage
        return "Нет данных"
    except Exception as e:
        logger.error(f"Ошибка при получении плеча для {clean_symbol}: {str(e)}")
        return f"Ошибка: {str(e)}"

def get_perpetual_futures_with_leverage():
    futures = get_perpetual_futures_list()
    futures_with_leverage = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        leverage_results = list(executor.map(get_leverage, [symbol.replace('/', '').replace(':USDC', '').replace(':USDT', '') for symbol in futures]))

    for symbol, leverage in zip(futures, leverage_results):
        if leverage is not None:
            futures_with_leverage.append(f"{symbol} (Плечо: {leverage})")
        else:
            futures_with_leverage.append(f"{symbol} (Плечо: недоступно)")
        time.sleep(0.001)  # Добавляем небольшую задержку между запросами

    return futures_with_leverage

def set_leverage(symbol, leverage):
    logger.info(f"Установка плеча {leverage} для {symbol}")
    try:
        # Удаляем лишние части из символа
        clean_symbol = symbol.split(' ')[0].replace('/', '').replace(':USDC', '').replace(':USDT', '')
        exchange.fapiPrivatePostLeverage({
            'symbol': clean_symbol,
            'leverage': int(leverage)
        })
        logger.info(f"Плечо для {symbol} успешно установлено на {leverage}")
        return f"Плечо для {symbol} установлено на {leverage}"
    except Exception as e:
        logger.error(f"Ошибка при установке плеча для {symbol}: {str(e)}")
        return f"Ошибка: {str(e)}"

def set_leverage_all(leverage):
    logger.info(f"Установка плеча {leverage} для всех бессрочных фьючерсов (swap)")
    futures = get_perpetual_futures_list()
    results = []
    for symbol in futures:
        results.append(set_leverage(symbol, leverage))
    return "\n".join(results)

layout = [
    [sg.Text('Binance API Key:'), sg.InputText(key='-API_KEY-', size=(40, 1))],
    [sg.Text('Binance Secret Key:'), sg.InputText(key='-SECRET_KEY-', size=(40, 1))],
    [sg.Button('Инициализировать биржу', key='-INIT_EXCHANGE-')],
    [sg.Text('Управление Плечом', font=('Courier', 16), justification='center')],
    [sg.Button('Получить список фьючерсов', key='-GET_FUTURES-')],
    [sg.Listbox(values=[], size=(50, 10), key='-FUTURES_LIST-', enable_events=True)],
    [sg.Text('Выбранный фьючерс:'), sg.InputText(key='-SELECTED_FUTURE-', size=(20, 1))],
    [sg.Button('Проверить плечо', key='-CHECK_LEVERAGE-')],
    [sg.Text('Текущее плечо:'), sg.InputText(key='-CURRENT_LEVERAGE-', readonly=True, size=(10, 1))],
    [sg.Text('Установить плечо:'), sg.InputText(key='-NEW_LEVERAGE-', size=(10, 1))],
    [sg.Button('Установить плечо для выбранного', key='-SET_LEVERAGE-')],
    [sg.Button('Установить плечо для всех', key='-SET_LEVERAGE_ALL-')],
    [sg.Multiline(size=(60, 10), key='-OUTPUT-', autoscroll=True)],
    [sg.Button('Выход')]
]

window = sg.Window('Binance Бессрочные Фьючерсы - Управление Плечом', layout, font=('Courier', 12))

while True:
    event, values = window.read()

    if event == sg.WINDOW_CLOSED or event == 'Выход':
        break

    if event == '-INIT_EXCHANGE-':
        api_key = values['-API_KEY-']
        secret_key = values['-SECRET_KEY-']
        if initialize_exchange(api_key, secret_key):
            window['-OUTPUT-'].print("Биржа успешно инициализирована")
        else:
            window['-OUTPUT-'].print("Ошибка при инициализации биржи")

    if event == '-GET_FUTURES-':
        if not exchange:
            window['-OUTPUT-'].print("Сначала инициализируйте биржу")
            continue
        futures_with_leverage = get_perpetual_futures_with_leverage()
        window['-FUTURES_LIST-'].update(futures_with_leverage)
        window['-OUTPUT-'].print(f"Получено {len(futures_with_leverage)} бессрочных фьючерсов (swap)")

    if event == '-FUTURES_LIST-':  # Обработка выбора фьючерса из списка
        selected = values['-FUTURES_LIST-']
        if selected:
            window['-SELECTED_FUTURE-'].update(selected[0])

    if event == '-CHECK_LEVERAGE-':
        if not exchange:
            window['-OUTPUT-'].print("Сначала инициализируйте биржу")
            continue
        symbol = values['-SELECTED_FUTURE-']
        if symbol:
            leverage = get_leverage(symbol)
            window['-CURRENT_LEVERAGE-'].update(leverage)
            window['-OUTPUT-'].print(f"Текущее плечо для {symbol}: {leverage}")
        else:
            window['-OUTPUT-'].print("Выберите фьючерс из списка")

    if event == '-SET_LEVERAGE-':
        if not exchange:
            window['-OUTPUT-'].print("Сначала инициализируйте биржу")
            continue
        symbol = values['-SELECTED_FUTURE-']
        leverage = values['-NEW_LEVERAGE-']
        if symbol:
            result = set_leverage(symbol, leverage)
            window['-OUTPUT-'].print(result)
        else:
            window['-OUTPUT-'].print("Выберите фьючерс из списка")

    if event == '-SET_LEVERAGE_ALL-':
        if not exchange:
            window['-OUTPUT-'].print("Сначала инициализируйте биржу")
            continue
        leverage = values['-NEW_LEVERAGE-']
        result = set_leverage_all(leverage)
        window['-OUTPUT-'].print(result)

window['-OUTPUT-'].print("Работа программы завершена.")
window.close()