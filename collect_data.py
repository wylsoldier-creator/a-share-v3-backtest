"""A-share historical OHLCV collector. No lookahead adjustments are used in the backtest input."""
import argparse
import json
import math
import time
from datetime import date
from pathlib import Path
import pandas as pd

START = '20160101'
END = '20261117'
COLUMNS = {'日期':'date','开盘':'open','最高':'high','最低':'low','收盘':'close',
           '成交量':'volume','成交额':'amount','涨跌幅':'pct_change','换手率':'turnover_rate'}
NUMERIC = ['open','high','low','close','volume','amount','pct_change','turnover_rate']


def normalize(raw, code):
    if raw is None or raw.empty:
        raise ValueError('EMPTY_RESPONSE')
    df = raw.rename(columns=COLUMNS).copy()
    mandatory = ['date','open','high','low','close','volume','amount']
    missing = set(mandatory)-set(df.columns)
    if missing:
        raise ValueError('MISSING_COLUMNS:'+','.join(sorted(missing)))
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    for col in NUMERIC:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['code'] = code
    return df.sort_values('date').reset_index(drop=True)


def quality(df, start, end, adjusted=False):
    issues = []
    if df.empty:
        return ['EMPTY']
    if df['date'].isna().any(): issues.append('INVALID_DATE')
    if df['date'].duplicated().any(): issues.append('DUPLICATE_DATE')
    if df['date'].notna().all() and ((df['date'] < pd.Timestamp(start)) | (df['date'] > pd.Timestamp(end))).any():
        issues.append('OUT_OF_RANGE')
    if df[['open','high','low','close','volume','amount']].isna().any().any(): issues.append('MISSING_REQUIRED_NUMERIC')
    if (df[['open','high','low','close']] <= 0).any().any(): issues.append('NONPOSITIVE_PRICE')
    if (df[['volume','amount']] < 0).any().any(): issues.append('NEGATIVE_ACTIVITY')
    if (df['high'] < df[['open','close','low']].max(axis=1)).any() or (df['low'] > df[['open','close','high']].min(axis=1)).any():
        issues.append('OHLC_INCONSISTENT')
    if df['date'].notna().all() and (df['date'].dt.dayofweek >= 5).any(): issues.append('WEEKEND_SESSION')
    # Adjusted series can differ slightly from raw and are NOT suitable as execution prices.
    return issues


def get_factor_data(ak, code, start, end):
    """Independent vendor adjustment factors, if available; never infer them from rounded adjusted OHLC."""
    prefix = 'sh' if code.startswith('6') else 'sz'
    result = {}
    for kind in ('qfq-factor','hfq-factor'):
        try:
            frame = ak.stock_zh_a_daily(symbol=prefix+code, adjust=kind)
            if frame is None or frame.empty:
                result[kind] = {'status':'unavailable'}
                continue
            frame = frame.copy()
            if 'date' not in frame.columns:
                result[kind] = {'status':'unavailable', 'reason':'missing date column'}
                continue
            frame['date'] = pd.to_datetime(frame['date'], errors='coerce')
            frame = frame.loc[frame.date.between(pd.Timestamp(start),pd.Timestamp(end))].sort_values('date')
            if frame.empty or frame.date.isna().any() or frame.date.duplicated().any():
                result[kind] = {'status':'invalid'}
            else:
                result[kind] = {'status':'ok','data':frame}
        except Exception as exc:
            result[kind] = {'status':'unavailable','reason':str(exc)[:180]}
    return result


def collect(codes, root, start=START, end=END, pause=1.2, factors=True, fetch=None, factor_fetch=None):
    if fetch is None:
        import akshare as ak
        fetch = lambda code, adj: ak.stock_zh_a_hist(symbol=code,period='daily',start_date=start,end_date=end,adjust=adj)
        factor_fetch = (lambda code: get_factor_data(ak,code,start,end)) if factors else None
    root = Path(root)
    report = {'start':start,'end':end,'requested':len(codes),'stocks':{},'schema':'v3-data-1',
              'note':'qfq/hfq are vendor adjusted reference series; never execute trades at adjusted prices.'}
    for code in codes:
        entry = {'status':'ok','series':{},'factors':{}}
        staged = {}
        for adj, label in (('', 'raw'),('qfq','qfq'),('hfq','hfq')):
            try:
                df = normalize(fetch(code,adj),code)
                issues = quality(df,start,end,adjusted=bool(adj))
                entry['series'][label] = {'rows':len(df),'issues':issues,
                    'first':str(df.date.iloc[0].date()),'last':str(df.date.iloc[-1].date())}
                if issues:
                    entry['status'] = 'failed'
                else:
                    staged[label] = df
            except Exception as exc:
                entry['series'][label] = {'issues':[str(exc)[:220]]}
                entry['status'] = 'failed'
            if pause: time.sleep(pause)
        if entry['status']=='ok':
            raw_dates = staged['raw']['date']
            for label in ('qfq','hfq'):
                if not raw_dates.equals(staged[label]['date']):
                    entry['series'][label]['issues'].append('DATES_DIFFER_FROM_RAW')
                    entry['status']='failed'
        if entry['status']=='ok':
            for label,df in staged.items():
                folder = root / ('data' if label=='raw' else f'data_adjusted/{label}')
                folder.mkdir(parents=True,exist_ok=True)
                target=folder/f'{code}.csv'
                tmp=target.with_suffix('.csv.tmp')
                df.to_csv(tmp,index=False,date_format='%Y-%m-%d',float_format='%.8f')
                tmp.replace(target)
        if factors and factor_fetch:
            for kind,info in factor_fetch(code).items():
                entry['factors'][kind] = {k:v for k,v in info.items() if k!='data'}
                if info.get('status')=='ok':
                    folder=root/'data_factors';folder.mkdir(parents=True,exist_ok=True)
                    target=folder/f'{code}_{kind}.csv'
                    tmp=target.with_suffix('.csv.tmp')
                    info['data'].to_csv(tmp,index=False,date_format='%Y-%m-%d')
                    tmp.replace(target)
        report['stocks'][code] = entry
    report['successful'] = sum(v['status']=='ok' for v in report['stocks'].values())
    report['failed'] = report['requested']-report['successful']
    (root/'reports').mkdir(parents=True,exist_ok=True)
    (root/'reports'/'data_quality.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--codes-file',default='config/stocks.txt')
    p.add_argument('--start',default=START)
    p.add_argument('--end',default=END)
    p.add_argument('--root',default='.')
    p.add_argument('--pause',type=float,default=1.2)
    p.add_argument('--skip-factors',action='store_true')
    a=p.parse_args()
    codes=[line.strip() for line in Path(a.codes_file).read_text().splitlines() if line.strip() and not line.startswith('#')]
    if len(codes)!=28 or len(set(codes))!=28 or any(len(c)!=6 or not c.isdigit() for c in codes):
        raise SystemExit('STOCK_POOL_INCOMPLETE: config/stocks.txt must contain exactly 28 unique six-digit tickers')
    report=collect(codes,a.root,a.start,a.end,a.pause,not a.skip_factors)
    print(json.dumps({'requested':report['requested'],'successful':report['successful'],'failed':report['failed']},ensure_ascii=False))
    if report['failed']: raise SystemExit(1)

if __name__=='__main__': main()
