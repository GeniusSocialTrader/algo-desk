import subprocess, time, glob, urllib.request, MetaTrader5 as mt5
BROKERS = [
    ("https://download.mql5.com/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe", "Exness-MT5Trial"),
    ("https://download.mql5.com/cdn/web/pepperstone.group.limited/mt5/pepperstone5setup.exe", "Pepperstone-Demo"),
    ("https://download.mql5.com/cdn/web/raw.trading.ltd/mt5/icmarketssc5setup.exe", "ICMarketsSC-Demo"),
]
for i, (url, srv) in enumerate(BROKERS):
    d = f"D:\\b{i}"
    try:
        urllib.request.urlretrieve(url, f"D:\\setup{i}.exe")
    except Exception as e:
        print(f"{srv}: installer download failed {e}", flush=True); continue
    t = time.time()
    p = subprocess.Popen([f"D:\\setup{i}.exe", "/auto", f"/path:{d}"])
    try: p.wait(400)
    except Exception: print("installer still running", flush=True)
    time.sleep(5); subprocess.run("taskkill /F /IM terminal64.exe", shell=True, capture_output=True); time.sleep(3)
    print(f"{srv}: installed in {time.time()-t:.0f}s, servers.dat:", glob.glob(d + r"\Config\servers.dat"), flush=True)
    t = time.time()
    ok = mt5.initialize(d + r"\terminal64.exe", login=12345678, password="wrong-pass-1", server=srv, portable=True, timeout=90000)
    print(f"{srv}: initialize {ok} {mt5.last_error()} {time.time()-t:.1f}s", flush=True)
    mt5.shutdown(); subprocess.run("taskkill /F /IM terminal64.exe", shell=True, capture_output=True); time.sleep(3)
    for f in glob.glob(d + r"\logs\2*.log"):
        for l in open(f, encoding="utf-16", errors="ignore").read().splitlines()[-5:]:
            print("   log:", l.split("\t", 3)[-1], flush=True)
