import argparse
from pathlib import Path
from src.backtest import backtest,load_csv

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-dir',default='data')
    p.add_argument('--output-dir',default='output')
    a=p.parse_args()
    paths=sorted(Path(a.data_dir).glob('*.csv'))
    if not paths:
        print('NO_DATA: no historical CSVs; no performance estimates generated')
        return
    Path(a.output_dir).mkdir(parents=True,exist_ok=True)
    for path in paths:
        eq,trades=backtest(load_csv(path))
        eq.to_csv(Path(a.output_dir)/f'{path.stem}_equity.csv',index=False)
        trades.to_csv(Path(a.output_dir)/f'{path.stem}_trades.csv',index=False)
        print(path.stem,len(eq),len(trades))
if __name__=='__main__': main()
