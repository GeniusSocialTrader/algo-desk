import os, shutil, subprocess, time, glob, MetaTrader5 as mt5
for srv in ["ICMarketsSC-Demo", "Exness-MT5Trial", "Pepperstone-Demo", "NoSuchBroker-Server"]:
    d = "D:\\t_" + srv.replace("-", "_")
    shutil.copytree(r"C:\Program Files\MetaTrader 5", d)
    t = time.time()
    ok = mt5.initialize(d + r"\terminal64.exe", login=12345678, password="wrong-pass-1", server=srv, portable=True, timeout=90000)
    print(f"{srv}: {ok} {mt5.last_error()} {time.time()-t:.1f}s", flush=True)
    mt5.shutdown()
    subprocess.run("taskkill /F /IM terminal64.exe", shell=True, capture_output=True)
    time.sleep(3)
    for f in glob.glob(d + r"\logs\2*.log"):
        lines = open(f, encoding="utf-16", errors="ignore").read().splitlines()
        for l in lines[-8:]:
            print("   log:", l.split("\t", 3)[-1], flush=True)
