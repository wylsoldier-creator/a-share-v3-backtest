import pandas as pd
from src.collect_data import normalize, quality, collect

def sample():
    return pd.DataFrame({'日期':['2026-11-16','2026-11-17'],'开盘':[10,11], '最高':[11,12],
        '最低':[9,10], '收盘':[10.5,11.5], '成交量':[100,200], '成交额':[10000,20000]})

def test_normalization_and_quality():
    df=normalize(sample(),'300528')
    assert quality(df,'20160101','20261117')==[]
    assert df.code.iloc[0]=='300528'

def test_duplicate_rejected():
    df=normalize(pd.concat([sample(),sample().iloc[:1]],ignore_index=True),'300528')
    assert 'DUPLICATE_DATE' in quality(df,'20160101','20261117')

def test_fail_closed_does_not_write_bad_data(tmp_path):
    bad=sample();bad.loc[0,'最高']=1
    result=collect(['300528'],tmp_path,fetch=lambda code,adj:bad, pause=0, factors=False)
    assert result['failed']==1
    assert not (tmp_path/'data'/'300528.csv').exists()
    assert (tmp_path/'reports'/'data_quality.json').exists()

def test_success_writes_three_series(tmp_path):
    result=collect(['300528'],tmp_path,fetch=lambda code,adj:sample(),pause=0,factors=False)
    assert result['successful']==1
    assert (tmp_path/'data'/'300528.csv').exists()
    assert (tmp_path/'data_adjusted/qfq'/'300528.csv').exists()
    assert (tmp_path/'data_adjusted/hfq'/'300528.csv').exists()
