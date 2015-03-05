from match import CosineQuery
from profile import Dictionary
from glob import glob
from profile import SemanticProfile
import sys, codecs, dblp, os
import texttable as tt
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from cStringIO import StringIO

def convert_pdf_to_txt(path):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = file(path, 'rb')
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
    return "".join(text.split("\n"))

__author__ = 'nilesh'

import cPickle, pickle
import nltk, re
from nltk.tokenize import RegexpTokenizer
from nltk.stem.porter import PorterStemmer

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

def getAuthor(authorName):
    authorName = authorName.strip()
    authors = dblp.search(authorName)
    if len(authors) < 1:
        print "Sorry, no author found for query %s" % authorName
        return None
    elif len(authors) == 1:
        author = authors[0]
        print "Author found: %s" % author.name
        return author
    else:
        n = len(authors)
        print "Multiple authors found for %s. Please disambiguate:" % authorName
        print "\n".join("%d. %s" % (i, author) for i, author in zip(range(1, n+1), (a.name for a in authors)))
        selection = -1
        while selection < 1 or selection > n:
            try:
                selection = int(raw_input("Enter a number in [1..%d] to select an author: " % n))
                # selection = 2
            except ValueError:
                pass
        return authors[selection - 1]

def getTopAuthors(authors, docs, concepts, results, numAuthors, numDocsPerAuthor):
    currentAuthor = None
    authorScores = []
    authorDocs = {}
    currentScore = 0.0
    count = 0
    currentAuthorDocs = []

    for i in range(len(authors)):
        a = authors[i]
        if a != currentAuthor:
            if currentAuthor != None:
                # Save total score of current author
                authorScores.append((currentAuthor, currentScore))
                # Save best k docs of current author with their scores
                currentAuthorDocs = filter(lambda x: x[1] > 0.0, currentAuthorDocs)
                authorDocs[currentAuthor] = sorted(currentAuthorDocs, key=lambda x: x[1], reverse=True)[:numDocsPerAuthor]

            # Get new author, reset docs and total score
            currentAuthor = a
            currentAuthorDocs = []
            currentScore = 0.0
            count = 0

        currentAuthorDocs += [(docs[i], results[i], concepts[i])]
        currentScore += results[i]
        count += 1

    # Save total score of current author
    authorScores.append((currentAuthor, currentScore))
    # Save best k docs of current author with their scores
    currentAuthorDocs = filter(lambda x: x[1] > 0.0, currentAuthorDocs)
    authorDocs[currentAuthor] = sorted(currentAuthorDocs, key=lambda x: x[1], reverse=True)[:numDocsPerAuthor]

    # print authorScores, authorDocs

    bestAuthors = sorted(authorScores, key=lambda x: x[1], reverse=True)[:numAuthors]
    auths = [i for i, j in bestAuthors]
    return zip(bestAuthors, [authorDocs[a] for a in auths])


def main():
    # authorsListFile = "/Users/nilesh/UoB/code/scholar-match/python/authors2.txt" #sys.argv[1]
    # queryDocFilesGlob = "/Users/nilesh/UoB/code/scholar-match/python/queries.txt" #sys.argv[2]
    knowledgeBaseFilesGlob = "enc/part*" #sys.argv[3]
    knowledgeBaseIndexFile = "enc/emldmindex.main"
    numAuthors = 5
    numTitles = 3

    authorsListFile = sys.argv[1]
    queryDocFilesGlob = sys.argv[2]
    # knowledgeBaseFilesGlob = sys.argv[3]
    # knowledgeBaseIndexFile = sys.argv[4]
    numAuthors = int(sys.argv[3])
    numTitles = int(sys.argv[4])
    cacheDir = sys.argv[5]

    try:
        authors, docs, labels = pickle.load(open("docsdum", "rb"))
    except:
        print "Reading authors list..."
        authors = []
        docs = []
        labels = []
        count = 0
        with codecs.open(authorsListFile, "r", encoding='utf-8') as fp:
            for a in fp:
                author = getAuthor(a)
                # print author.name
                if author == None: continue
                try:
                    publications = pickle.load(open(os.path.join(cacheDir, author.name), "rb"))
                except:
                    publications = [unicode(p.title) for p in author.publications]
                    pickle.dump(publications, open(os.path.join(cacheDir, author.name), "wb"))
                # author.load_data()
                for p in publications:
                    authors += [unicode(author.name)]
                    docs += [p]
                    labels.append(count)
                    count += 1

        # docs = labels

        # print (authors, docs, labels)
        # pickle.dump((authors, docs, labels), open("docsdump", "wb"))

    print "Reading query files..."
    queries = []
    for f in glob(queryDocFilesGlob):
        if f.endswith(".pdf"):
            text = convert_pdf_to_txt(f)
        else:
            print "File %s does not have extension .pdf. Assuming text." % f
            with codecs.open(f, "r", encoding='utf-8') as fp:
                text = fp.read()
        queries += [(f, text)]
    #
    print "Building semantic interpreter..."
    topics, enc = getEnc(knowledgeBaseFilesGlob, knowledgeBaseIndexFile)
    encDictionary = Dictionary(enc, [i[:-9] for i in topics])

    print "Building author profiles..."
    docsDictionary = Dictionary(docs, labels)
    p = SemanticProfile(docsDictionary, encDictionary)
    q = CosineQuery(p)
    try:
        pickle.dump(p, open("authorsdump2", "wb"))
    except Exception as e:
        print e

    # p = pickle.load(open("authorsdump2", "rb"))
    # q = CosineQuery(p)
    # a = p.transformRawDocuments(["ROC curves in cost space"]).toarray()[0]
    # for i in range(len(a)):
    #     if a[i] != 0.0:
    #         print topics[i], a[i]
    # for query in queries:
    #     print query[1]
    #     print [(i, j, c) for i, j, k, c in q.queryContributions(p.transformRawDocuments(query[1]), topConcepts=3, numResults=top)]

    for f, query in queries:
        print "Computing matches for file %s" % f
        print
        results = q.queryContributions(p.transformRawDocuments([query]), topConcepts=3)
        results = sorted(results, key=lambda x: x[0])
        for (author, score), titles in getTopAuthors(authors, docs, [i[3] for i in results], [i[1] for i in results], numAuthors, numTitles):
            print "Author: %s\nAvg. Cosine Score: %f" % (author, score)
            table = tt.Texttable()
            table.header(["Paper", "Cosine Score", "Concepts"])
            for title, tscore, concepts in titles:
                table.add_row([title, tscore, " | ".join(concepts.keys())])
            table.set_cols_width([60,10,100])
            table.set_cols_align(['l','l','l'])
            print table.draw()
            print "\n"

if __name__ == '__main__':
    main()
