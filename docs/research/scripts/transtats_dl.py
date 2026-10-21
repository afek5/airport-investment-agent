# Usage: python3 -I transtats_dl.py <gnoyr_VQ> <year> <periodValue> <outzip> FIELD1 FIELD2 ...
import sys, re, urllib.request, urllib.parse, http.cookiejar, time
vq, year, period, out = sys.argv[1:5]; fields = sys.argv[5:]
base = f"https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ={vq}&QO_fu146_anzr=Nv4%20Pn44vr45"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0 (research script)")]
t = op.open(base, timeout=90).read().decode("utf-8", "ignore")
def hid(n):
    m = re.search(r'name="%s"[^>]*value="([^"]*)"' % n, t) or re.search(r'id="%s" value="([^"]*)"' % n, t)
    return m.group(1) if m else ""
sel = re.search(r'<select[^>]*name="cboPeriod"[^>]*>(.*?)</select>', t, re.S)
print("period options:", re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel.group(1))[:14] if sel else None)
data = {"__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
        "__VIEWSTATE": hid("__VIEWSTATE"), "__VIEWSTATEGENERATOR": hid("__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": hid("__EVENTVALIDATION"),
        "txtSearch": "", "cboGeography": __import__("os").environ.get("GEO","All"), "cboYear": year, "cboPeriod": period,
        "btnDownload": "Download"}
for f in fields: data[f] = "on"
t0 = time.time()
r = op.open(base, data=urllib.parse.urlencode(data).encode(), timeout=300)
body = r.read()
print("status", r.status, "ctype", r.headers.get("Content-Type"), "bytes", len(body), "secs", round(time.time()-t0,1), "final url", r.geturl())
open(out, "wb").write(body)
