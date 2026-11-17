import pandas as pd
from src.backtest import indicators,backtest

def test_no_lookahead():
    close=[10.0]*12+[10.1+i*0.2 for i in range(12)]
    df=pd.DataFrame({'date':pd.date_range('2026-01-01',periods=len(close),freq='B'),'open':close,'high':[v+0.2 for v in close],'low':[v-0.2 for v in close],'close':close,'volume':[1000]*len(close)})
    x=indicators(df)
    eq,trades=backtest(df)
    assert len(eq)==len(df)
    assert pd.isna(x.loc[0,'ma10'])
    for _,t in trades[trades.side=='BUY'].iterrows():
        i=x.index[x.date.dt.strftime('%Y-%m-%d')==t.date][0]
        assert i>0 and bool(x.loc[i-1,'signal'])
