import sys, time, MetaTrader5 as mt5
mode = sys.argv[1]
P = r"D:\mt5a\terminal64.exe" if mode == "A" else r"D:\mt5b\terminal64.exe"
t = time.time()
if mode == "A":
    ok = mt5.initialize(P, login=12345678, password="wrong-pass-1", server="MetaQuotes-Demo", portable=True, timeout=120000)
else:
    ok = mt5.initialize(P, portable=True, timeout=120000)
print(mode, "initialize:", ok, mt5.last_error(), f"{time.time()-t:.1f}s", flush=True)
ti = mt5.terminal_info()
print(mode, "terminal_info:", ti and {k: getattr(ti, k) for k in ("connected", "build", "path")}, flush=True)
for srv in ["MetaQuotes-Demo", "ICMarketsSC-Demo", "Exness-MT5Trial", "NoSuchBroker-Server"]:
    t = time.time()
    r = mt5.login(12345678, password="wrong-pass-1", server=srv, timeout=45000)
    print(f"{mode} login probe {srv}: {r} {mt5.last_error()} {time.time()-t:.1f}s", flush=True)
mt5.shutdown()
