from pathlib import Path
p=Path('src/collect_data.py')
s=p.read_text(encoding='utf-8')
s=s.replace('ak.stock_zh_a_hist(symbol=code,period=', 'ak.stock_zh_a_hist_em(symbol=code,period=')
s=s.replace('ak.stock_zh_a_daily(symbol=prefix+code, adjust=kind)', 'ak.stock_zh_a_hist_sina(symbol=prefix+code, adjust=kind)')
s=s.replace("    print(json.dumps({'requested':report['requested'],'successful':report['successful'],'failed':report['failed']},ensure_ascii=False))", "    print(json.dumps({'requested':report['requested'],'successful':report['successful'],'failed':report['failed']},ensure_ascii=False))\n    for code, item in report['stocks'].items():\n        if item['status'] != 'ok':\n            print(json.dumps({'code':code,'series':item['series']},ensure_ascii=False),flush=True)")
p.write_text(s,encoding='utf-8')
print('Patched:',p)
