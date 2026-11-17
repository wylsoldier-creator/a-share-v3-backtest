from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class Config:
    initial_cash: float = 300000
    risk_fraction: float = 0.01
    commission: float = 0.0001
    stamp_tax: float = 0.0005  # Only applicable to dates with this rate
    slippage_bps: float = 5
    lot: int = 100

def indicators(df):
    x = df.sort_values('date').reset_index(drop=True).copy()
    for n in (5, 10):
        x[f'ma{n}'] = x.close.rolling(n).mean()
        x[f'volume_ma{n}'] = x.volume.rolling(n).mean()
    x['dif'] = x.close.ewm(span=12,adjust=False).mean()-x.close.ewm(span=26,adjust=False).mean()
    x['dea'] = x.dif.ewm(span=9,adjust=False).mean()
    x['macd'] = 2*(x.dif-x.dea)
    x['structure_low'] = x.low.rolling(10).min()
    x['signal'] = (x.ma5>x.ma10)&(x.ma5.shift(1)<=x.ma10.shift(1))&(x.macd>0)
    return x

def load_csv(path):
    x = pd.read_csv(path,parse_dates=['date'])
    required = {'date','open','high','low','close','volume'}
    if not required.issubset(x):
        raise ValueError(f'Missing: {required-set(x)}')
    if x.date.duplicated().any() or (x[['open','high','low','close']]<=0).any().any():
        raise ValueError('Invalid prices or duplicate dates')
    if (x.high < x[['open','close','low']].max(axis=1)).any() or (x.low > x[['open','close','high']].min(axis=1)).any():
        raise ValueError('Inconsistent OHLC')
    return x.sort_values('date').reset_index(drop=True)

def backtest(df,cfg=None):
    cfg=cfg or Config()
    x=indicators(df)
    cash=cfg.initial_cash
    shares=0
    stop=np.nan
    entry_index=-1
    trades=[]
    curve=[]
    for i,r in x.iterrows():
        date=str(r.date.date()) if hasattr(r.date,'date') else str(r.date)
        if shares and i>entry_index and r.low<=stop:
            price=min(r.open,stop)*(1-cfg.slippage_bps/10000)
            fee=shares*price*(cfg.commission+cfg.stamp_tax)
            cash+=shares*price-fee
            trades.append(dict(date=date,side='SELL',shares=shares,price=price,fee=fee))
            shares=0
            stop=np.nan
        if not shares and i>0 and bool(x.loc[i-1,'signal']):
            structure=x.loc[i-1,'structure_low']
            price=r.open*(1+cfg.slippage_bps/10000)
            if np.isfinite(structure) and price>structure:
                by_risk=int((cash*cfg.risk_fraction/(price-structure))//cfg.lot)*cfg.lot
                by_cash=int((cash/(price*(1+cfg.commission)))//cfg.lot)*cfg.lot
                qty=min(by_risk,by_cash)
                if qty>0:
                    fee=qty*price*cfg.commission
                    cash-=qty*price+fee
                    shares=qty
                    stop=structure
                    entry_index=i
                    trades.append(dict(date=date,side='BUY',shares=qty,price=price,fee=fee,stop=stop))
        curve.append(dict(date=date,cash=cash,shares=shares,equity=cash+shares*r.close))
    return pd.DataFrame(curve),pd.DataFrame(trades)
