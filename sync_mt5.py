"""Delton's Desk: free sync. Runs on a GitHub Actions Windows runner (see sync.yml).

Logs in to each MT5 account with its investor (read-only) password through the official MetaTrader5
Python package, and sends deals, open positions and an equity snapshot to the same insert-only database
functions the paid sync and the EA use. Duplicates are skipped by the database, so every run can safely
resend the full history.

Secrets (GitHub repo > Settings > Secrets and variables > Actions):
  SUPABASE_URL   https://xxxx.supabase.co
  SUPABASE_KEY   the publishable key (sb_publishable_...). It can only add rows, never read or change them.
  MT5_ACCOUNTS   one account per line:  login | investor password | server
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

TERMINAL = os.environ.get("MT5_TERMINAL", r"C:\MT5\terminal64.exe")

# MT5 deal type / entry codes -> the words the database uses (same as the EA)
TYPES = {0: "buy", 1: "sell", 2: "balance", 3: "credit", 4: "charge", 5: "correction", 6: "bonus", 7: "commission",
         8: "commission", 9: "commission", 10: "commission", 11: "commission", 13: "interest"}
ENTRIES = {0: "in", 1: "out", 2: "inout", 3: "outby"}


def btime(sec):
    """MT5 times are broker server time counted as if it were UTC."""
    return datetime.fromtimestamp(int(sec), timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if sec else None


def parse_accounts(text):
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("|") < 2:
            raise ValueError("Each MT5_ACCOUNTS line must be: login | investor password | server")
        login, rest = line.split("|", 1)
        password, server = rest.rsplit("|", 1)
        out.append((int(login.strip()), password.strip(), server.strip()))
    return out


def map_deal(d, login, currency):
    return {"account": login, "deal": int(d.ticket), "platform": "MT5", "currency": currency, "time": btime(d.time),
            "type": TYPES.get(d.type, f"other{d.type}"), "entry": ENTRIES.get(d.entry, ""), "position": int(d.position_id),
            "ord": int(d.order), "symbol": d.symbol or "", "volume": d.volume, "price": d.price,
            "sl": getattr(d, "sl", None), "tp": getattr(d, "tp", None), "commission": d.commission,
            "fee": getattr(d, "fee", 0.0), "swap": d.swap, "profit": d.profit, "magic": int(d.magic), "comment": d.comment or ""}


def map_position(p):
    return {"ticket": int(p.ticket), "symbol": p.symbol, "type": "sell" if p.type == 1 else "buy", "lots": p.volume,
            "open_time": btime(p.time), "open_price": p.price_open, "price": p.price_current, "sl": p.sl, "tp": p.tp,
            "profit": p.profit, "swap": p.swap, "commission": 0.0, "magic": int(p.magic), "comment": p.comment or ""}


def equity_rows(login, broker_now_sec, info, positions):
    """One 5-minute bucket: the whole account (magic -1) plus one row per EA (magic + comment), like the EA sends."""
    bucket = btime(broker_now_sec - broker_now_sec % 300)
    bal, eq = info.balance, info.equity
    rows = [{"account": login, "bucket": bucket, "magic": -1, "comment": "", "balance": bal, "equity_min": eq,
             "equity_max": eq, "floating_min": round(eq - bal, 2), "open_max": len(positions)}]
    groups = {}
    for p in positions:
        g = groups.setdefault((p["magic"], p["comment"]), [0.0, 0])
        g[0] += (p["profit"] or 0) + (p["swap"] or 0)
        g[1] += 1
    for (magic, comment), (fl, n) in groups.items():
        rows.append({"account": login, "bucket": bucket, "magic": magic, "comment": comment, "balance": bal,
                     "equity_min": eq, "equity_max": eq, "floating_min": round(fl, 2), "open_max": n})
    return rows


def rpc(fn, payload):
    url, key = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_KEY"].strip()
    req = urllib.request.Request(f"{url}/rest/v1/rpc/{fn}", data=json.dumps(payload).encode(), method="POST",
                                 headers={"apikey": key, "Content-Type": "application/json"})
    for tries in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"0")
        except urllib.error.HTTPError as e:
            if e.code < 500 or tries == 2:
                raise RuntimeError(f"{fn} -> {e.code} {e.read()[:300]!r}") from None
        except urllib.error.URLError:
            if tries == 2:
                raise
        time.sleep(3 * (tries + 1))


def broker_now(mt5, symbols):
    """Broker server time from the freshest tick; None when the market is closed (no equity snapshot then)."""
    newest = 0
    for s in symbols:
        mt5.symbol_select(s, True)
        t = mt5.symbol_info_tick(s)
        if t and t.time > newest:
            newest = t.time
    return newest or None


def sync_account(mt5, login, password, server):
    if not mt5.login(login, password=password, server=server, timeout=60000):
        raise RuntimeError(f"login failed {mt5.last_error()}")
    info = mt5.account_info()
    end = datetime.now(timezone.utc) + timedelta(days=2)
    deals, last = [], -1
    for _ in range(10):  # the terminal downloads history in the background; wait until the count stops growing
        deals = mt5.history_deals_get(datetime(2000, 1, 1, tzinfo=timezone.utc), end) or ()
        if len(deals) == last:
            break
        last = len(deals)
        time.sleep(3)
    rows = [map_deal(d, login, info.currency) for d in deals]
    added = sum(rpc("push_deals", {"rows": rows[i:i + 500]}) for i in range(0, len(rows), 500))
    positions = [map_position(p) for p in (mt5.positions_get() or ())]
    rpc("push_positions", {"acct": login, "rows": positions})
    syms = list({p["symbol"] for p in positions} | {d.symbol for d in deals[-50:] if d.symbol})[:8] or ["EURUSD"]
    now = broker_now(mt5, syms)
    if now and abs(now - time.time()) < 15 * 3600:
        rpc("push_equity", {"rows": equity_rows(login, now, info, positions)})
    return {"account": login, "deals": len(rows), "new": added, "open": len(positions), "equity": info.equity,
            "equity_saved": bool(now)}


def main():
    import MetaTrader5 as mt5
    accounts = parse_accounts(os.environ.get("MT5_ACCOUNTS"))
    if not accounts:
        sys.exit("Add the MT5_ACCOUNTS secret first.")
    first = accounts[0]
    if not mt5.initialize(TERMINAL, login=first[0], password=first[1], server=first[2], portable=True, timeout=120000):
        err = mt5.last_error()
        hint = (" The terminal does not know this server name. Set the MT5_INSTALLER_URL variable to your broker's"
                " MT5 download link (see the guide).") if err[0] == -10005 else ""
        sys.exit(f"Could not start MetaTrader 5 for {first[0]} on {first[2]}: {err}.{hint}")
    failed = 0
    for login, password, server in accounts:
        try:
            print(json.dumps(sync_account(mt5, login, password, server)), flush=True)
        except Exception as e:  # one bad account must not stop the others
            failed += 1
            print(json.dumps({"account": login, "error": str(e)}), flush=True)
    mt5.shutdown()
    if failed:
        sys.exit(f"{failed} account(s) failed, see above.")


if __name__ == "__main__":
    main()
