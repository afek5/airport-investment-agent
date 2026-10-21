# stdlib xlsx reader: python3 -I xlsx_peek.py file.xlsx nheader [filter_substr...]
import sys, zipfile, re, xml.etree.ElementTree as ET
z=zipfile.ZipFile(sys.argv[1]); ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ss=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(ns+'si')] if 'xl/sharedStrings.xml' in z.namelist() else []
sheets=[n for n in z.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml',n)]; print('sheets',sheets)
nh=int(sys.argv[2]); flt=sys.argv[3:]
n=0; shown=0
for ev,el in ET.iterparse(z.open(sheets[0])):
    if el.tag==ns+'row':
        vals=[]
        for c in el.iter(ns+'c'):
            v=c.find(ns+'v'); t=c.get('t')
            if v is None:
                i=c.find('.//'+ns+'t'); vals.append(i.text if i is not None else '')
            else: vals.append(ss[int(v.text)] if t=='s' else v.text)
        n+=1
        if n<=nh or (flt and all(f in vals for f in flt) and shown<6): print(vals[:40]); shown+= n>nh
        el.clear()
print('total rows',n)
