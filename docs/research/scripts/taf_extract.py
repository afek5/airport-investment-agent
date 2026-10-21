import sys,zipfile,xml.etree.ElementTree as ET
z=zipfile.ZipFile(sys.argv[1]); ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
want=set(sys.argv[2].split(',')); yrs_w=set(sys.argv[3].split(','))
out=[]; yrs=set(); scen=set(); hdr=None
for ev,el in ET.iterparse(z.open('xl/worksheets/sheet1.xml')):
    if el.tag==ns+'row':
        vals=[]
        for c in el.iter(ns+'c'):
            v=c.find(ns+'v')
            vals.append(v.text if v is not None else ''.join(t.text or '' for t in c.iter(ns+'t')))
        if hdr is None: hdr=vals
        else:
            yrs.add(vals[2]); scen.add(vals[1])
            if vals[0].strip() in want and vals[2] in yrs_w: out.append(vals)
        el.clear()
print(hdr); print('years',min(yrs),max(yrs),'scenarios',scen)
for o in out: print(o)
