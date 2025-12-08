import json
import yfinance as yf
#from tabulate2 import tabulate



ticker = yf.Ticker("AMZN")
print(type(ticker))
info = ticker.info
fastinfo = ticker.fast_info
#history = dat.history(period="1y", interval='1d')

#print(json.dumps(ticker, indent=2))