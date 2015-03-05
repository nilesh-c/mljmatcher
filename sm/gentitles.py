__author__ = 'nilesh'

from xml.etree.ElementTree import iterparse, XMLParser
import htmlentitydefs
import argparse, os

parser = argparse.ArgumentParser(description='Parse DBLP XML file and generate an SQLite DB of publication key-title pairs.')
parser.add_argument('xmldump', metavar='X', type=str, nargs=1,
                   help='path to existing DBLP XML dump')
parser.add_argument('db', metavar='D', type=str, nargs=1,
                   help='path to create SQLite database at (overwrites if already exists)')

args = parser.parse_args()

xmldump = args.xmldump[0]
dbname = args.db[0]
if os.path.isfile(dbname):
    os.remove(dbname)

class AllEntities:
    def __getitem__(self, key):
        return unichr(htmlentitydefs.name2codepoint[key])

parser = XMLParser()
parser.parser.UseForeignDTD(True)
parser.entity = AllEntities()

import sqlite3
conn = sqlite3.connect(dbname)
c = conn.cursor()
c.execute("CREATE TABLE Titles (key TEXT, title TEXT)")
c.execute("CREATE UNIQUE INDEX key_index ON Titles (key)")
conn.commit()

count = 0
for (event, node) in iterparse(xmldump, events=['start'], parser=parser):
    if node.tag in "article|inproceedings|proceedings|book|incollection|phdthesis|mastersthesis|www".split("|"):
        try:
            c.execute("INSERT INTO Titles(key, title) VALUES (?, ?)", (node.attrib['key'], node.find('title').text))
        except:
            pass
        if count % 5000 == 0:
            conn.commit()
            print "Inserted %d publications..." % count
        count += 1
    node.clear()