from sm.profile import Dictionary, SemanticProfile
from sm.match import CosineQuery
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from cStringIO import StringIO
import sqlite3
import dblp
from glob import glob
import nltk, re, codecs, os
from nltk.tokenize import RegexpTokenizer
from nltk.stem.porter import PorterStemmer
import numpy as np
from scipy.sparse import issparse
# tornado, nltk, dblp, pdfminer, sqlite3, scikit-learn
__author__ = 'nilesh'

def getWords(text):
    doc = re.sub(' +', ' ', text).replace('\n', ' ')
    tokens = RegexpTokenizer(r'\w+').tokenize(doc)
    tokens = [PorterStemmer().stem(i.lower()) for i in tokens if i not in nltk.corpus.stopwords.words('english') and not i.isdigit() and len(i) > 3]
    return " ".join(tokens)

def getEnc(encFiles, encIndexFile):
    encindex = {}
    numbertotopic = []
    with codecs.open(encIndexFile, encoding='utf-8') as ind:
        for i in ind:
            a = i.split("\t")
            number = int(a[0].strip())
            encindex[a[1].strip()] = number
            numbertotopic += [a[1].strip()]

    def loadCleanedAndSortBy(loadFromDir, sortby):
        # sortby is a mapping from filename to number
        arr = [None]*len(sortby)
        for loadFrom in glob(loadFromDir):
            with codecs.open(loadFrom, encoding='utf-8') as fp:
                for i in fp:
                    filename, text = i.split("\t")
                    filename = filename.split("/")[-1].replace('abs.txt', 'pdf.txt')
                    if filename in sortby:
                        arr[sortby[filename]] = text
                    else: pass #print (filename)
        return arr

    encArray = loadCleanedAndSortBy(encFiles, encindex)

    return numbertotopic, encArray

def getTopAuthors(authors, docs, concepts, results, numAuthors=-1, numDocsPerAuthor=-1):
    currentAuthor = None
    authorScores = []
    authorDocs = {}
    currentScore = 0.0
    count = 0
    currentAuthorDocs = []

    def appendAuthor(currentAuthorDocs):
        # Save total score of current author
        authorScores.append((currentAuthor, currentScore))
        # Save best k docs of current author with their scores
        currentAuthorDocs = filter(lambda x: x[1] > 0.0, currentAuthorDocs)
        if numDocsPerAuthor == -1:
            authorDocs[currentAuthor] = sorted(currentAuthorDocs, key=lambda x: x[1], reverse=True)
        else:
            authorDocs[currentAuthor] = sorted(currentAuthorDocs, key=lambda x: x[1], reverse=True)[:numDocsPerAuthor]

    for i in range(len(authors)):
        a = authors[i]
        if a != currentAuthor:
            if currentAuthor != None:
                appendAuthor(currentAuthorDocs)

            # Get new author, reset docs and total score
            currentAuthor = a
            currentAuthorDocs = []
            currentScore = 0.0
            count = 0

        currentAuthorDocs += [(docs[i], results[i], concepts[i])]
        currentScore += results[i]
        count += 1

    appendAuthor(currentAuthorDocs)

    # print authorScores, authorDocs

    if numAuthors == -1:
        bestAuthors = sorted(authorScores, key=lambda x: x[1], reverse=True)
    else:
        bestAuthors = sorted(authorScores, key=lambda x: x[1], reverse=True)[:numAuthors]
    auths = [i for i, j in bestAuthors]

    # normalize author scores so that sum of them is 1
    total = sum((j for i, j in bestAuthors))
    for i in range(len(bestAuthors)):
        author, score = bestAuthors[i]
        bestAuthors[i] = (author, score / total)

    return zip(bestAuthors, [authorDocs[a] for a in auths])

def extractTextFromPDF(pdfMime):
    """Extracts text from a PDF given in mime format (application/pdf).

    Args:
        pdfMime: String containing the PDF in mime format.

    Returns:
        Text extracted from the PDF.
    """
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = StringIO(pdfMime)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos=set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()
    return text.decode('utf-8')

# class DBLP():
#     def __init__(self):
#         self.conn = sqlite3.connect('titles.db')
#
#     def getTitlesForAuthor(self, authorString, authorString2=None):
#         return self.getTitles(self.getPublicationKeys(self.searchAuthor(authorString, authorString2)))
#
#     def searchAuthor(self, authorString, authorString2=None):
#         results = dblp.search(authorString)
#         if len(results) == 0:
#             if "(" in authorString2:
#                 authorString2 = authorString2[:authorString2.index("(")].strip()
#             return dblp.search(authorString2)[0]
#         else:
#             return results[0]
#
#     def getPublicationKeys(self, author):
#         return [p.key for p in author.publications]
#
#     def getTitles(self, publicationKeys):
#         c = self.conn.cursor()
#         c.execute("SELECT title FROM Titles WHERE key in (%s)" % ",".join("?"*len(publicationKeys)), publicationKeys)
#         results = c.fetchall()
#         c.close()
#         return results

class DBLP():
    def __init__(self, dbpath):
        self.dbpath = dbpath

    def getTitlesForAuthor(self, authorStrings):
        authorString, authorString2 = authorStrings
        conn = sqlite3.connect(self.dbpath)
        return authorString2, self.getTitles(self.getPublicationKeys(self.searchAuthor(authorString, authorString2)), conn=conn)

    def searchAuthor(self, authorString, authorString2=None):
        results = dblp.search(authorString)
        if len(results) == 0:
            if "(" in authorString2:
                authorString2 = authorString2[:authorString2.index("(")].strip()
            return dblp.search(authorString2)[0]
        elif len(results) > 1:
            return max(results, key=lambda x: len(x.publications))
        else:
            return results[0]

    def getPublicationKeys(self, author):
        return [p.key for p in author.publications]

    def getTitles(self, publicationKeys, conn):
        c = conn.cursor()
        c.execute("SELECT title FROM Titles WHERE key in (%s)" % ",".join("?"*len(publicationKeys)), publicationKeys)
        results = [i[0] for i in c.fetchall()]
        c.close()
        return results

class Matcher():
    # def __init__(self, authPubs, profile=True):
    #     self.authors = []
    #     self.docs = []
    #     self.labels = []
    #     count = 0
    #     for author, publications in authPubs:
    #         for publication in publications:
    #             if publication[0] != None:
    #                 self.authors.append(unicode(author))
    #                 self.docs.append(publication[0])
    #                 self.labels.append(count)
    #                 count += 1
    #
    #     if profile == True:
    #         self.buildSemanticInterpreter()
    #         self.buildAuthorProfiles()
    #
    # def __init__(self):
    def __init__(self, cachedir, encDirectory):
        self.cachedir = cachedir
        self.encDirectory = encDirectory
        self.builtAuthorProfiles = False
        self.builtConcatAuthorProfiles = False
        self.encDictionary = None

    def buildSemanticInterpreter(self):
        import cPickle as pickle
        print "Building semantic interpreter..."
        knowledgeBaseFilesGlob = os.path.join(os.path.dirname(os.path.realpath(__file__)), "kbases", self.encDirectory, "part*")
        knowledgeBaseIndexFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "kbases", self.encDirectory, "emldmindex.main")
        topics, enc = getEnc(knowledgeBaseFilesGlob, knowledgeBaseIndexFile)
        # self.encDictionary = Dictionary(enc, [i[:-9] for i in topics])
        try:
            if os.path.isfile(os.path.join(self.cachedir, self.encDirectory + ".authorProfiles")):
                self.encDictionary = 'notneeded'
                # return
            self.encDictionary = pickle.load(open(os.path.join(self.cachedir, self.encDirectory + ".encDictionary"), "rb"))
        except:
            self.encDictionary = Dictionary(enc, [i for i in topics])
            pickle.dump(self.encDictionary, open(os.path.join(self.cachedir, self.encDirectory + ".encDictionary"), "wb"))

    def buildConcatenatedAuthorProfiles(self, authPubs):
        import cPickle as pickle
        try:
            self.authorsc, self.docsc, self.labelsc, self.pc, self.qc = pickle.load(open(os.path.join(self.cachedir, self.encDirectory + ".authorProfilesConcat"), "rb"))
            print "Loaded cached concatenated profiles"
        except:
            print "Generating author profiles, no cache exists"
            self.authorsc = []
            self.docsc = []
            self.labelsc = []
            count = 0
            for author, publications in authPubs:
                self.authorsc.append(unicode(author))
                self.docsc.append("")
                self.labelsc.append(count)
                for publication in publications:
                    if publication != None:
                        self.docsc[count] += " " + publication
                count += 1

            print "Building concatenated author profiles..."
            docsDictionary = Dictionary(self.docsc, self.labelsc)
            self.pc = SemanticProfile(docsDictionary, self.encDictionary)
            self.qc = CosineQuery(self.pc)

            pickle.dump((self.authorsc, self.docsc, self.labelsc, self.pc, self.qc), open(os.path.join(self.cachedir, self.encDirectory + ".authorProfilesConcat"), "wb"))
        self.builtConcatAuthorProfiles = True

    def buildAuthorProfiles(self, authPubs):
        import cPickle as pickle
        try:
            self.authors, self.docs, self.labels, self.p, self.q = pickle.load(open(os.path.join(self.cachedir, self.encDirectory + ".authorProfiles"), "rb"))
            print "Loaded cached profiles"
        except:
            print "Generating author profiles, no cache exists"
            self.authors = []
            self.docs = []
            self.labels = []
            count = 0
            for author, publications in authPubs:
                for publication in publications:
                    if publication != None:
                        self.authors.append(unicode(author))
                        self.docs.append(publication)
                        self.labels.append(count)
                        count += 1

            print "Building author profiles..."
            docsDictionary = Dictionary(self.docs, self.labels)
            self.p = SemanticProfile(docsDictionary, self.encDictionary)
            self.q = CosineQuery(self.p)

            pickle.dump((self.authors, self.docs, self.labels, self.p, self.q), open(os.path.join(self.cachedir, self.encDirectory + ".authorProfiles"), "wb"))
        self.builtAuthorProfiles = True

    def queryConcat(self, queryText, topK=-1):
        results = self.qc.queryContributions(self.pc.transformRawDocument(queryText, K=topK))
        results = sorted(results, key=lambda x: x[1])
        results = {self.authorsc[label].split("||")[1]: (score, concepts) for label, score, _, concepts in results}
        # print results
        return results

    def getTopConcepts(self, queryText, topK=-1, topConcepts=-1):
        transformed = self.p.transformRawDocument(queryText, K=topK)

        if issparse(transformed):
            transformed = transformed.toarray()[0]

        if topConcepts == -1:
            concepts = np.argsort(transformed).tolist()
        else:
            concepts = np.argsort(transformed)[-topConcepts:].tolist()

        for i in concepts:
            if transformed[i] == 0.0:
                concepts.remove(i)

        return {self.p.conceptLabels[i]: transformed[i] for i in concepts}


    def query(self, queryText, topK=-1):
        numAuthors = -1
        numAuthors = -1
        numTitles = -1

        results = self.q.queryContributions(self.p.transformRawDocument(queryText, K=topK), topConcepts=-1)
        results = sorted(results, key=lambda x: x[0])
        # print results
        return getTopAuthors(self.authors, self.docs, [i[3] for i in results], [i[1] for i in results], numAuthors, numTitles)

        # for (author, score), titles in getTopAuthors(self.authors, self.docs, [i[3] for i in results], [i[1] for i in results], numAuthors, numTitles):
        #     print "Author: %s\nAvg. Cosine Score: %f" % (author, score)
        #     table = tt.Texttable()
        #     table.header(["Paper", "Cosine Score", "Concepts"])
        #     for title, tscore, concepts in titles:
        #         table.add_row([title, tscore, " | ".join(concepts.keys())])
        #     table.set_cols_width([60,10,100])
        #     table.set_cols_align(['l','l','l'])
        #     finalstr += table.draw() + "<br><br>"
        # return finalstr