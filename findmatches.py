import os, sys, time, codecs, json
import argparse
from glob import glob
from sm.util import DBLP, extractTextFromPDF, Matcher
from argparse import RawTextHelpFormatter
from tornado.template import Loader

__author__ = 'nilesh'
CACHEDIR = None

indexby = {1:'emltex_selected', 2:'emltex', 3:'emltexwiki_selected', 4:'emltexwiki', 5:'emlallwiki'}

def getCutoff(cutoff):
    if '-1' in cutoff:
        return None
    else:
        try:
            c = float(cutoff.strip())
            if c < 0:
                return None
            else:
                return c
        except:
            return None

def getAuthPubs(dblplist, dbpath):
    dblp = DBLP(dbpath)
    authPubs = []
    # print dblpsplit
    dblpAuthorsList = [i.split(",") for i in dblplist.split("\n") if i.strip() != '']
    for name, urlid in dblpAuthorsList:
        print "Fetching publications for author %s" % name
        try:
            with codecs.open(os.path.join(CACHEDIR, urlid.replace("/", "#").strip()), "r", encoding='utf-8') as cache:
                result = json.loads(cache.read())
                result[0] = "%s||%s" % (result[0], urlid)
            # with codecs.open("cache2/%s" % urlid.replace("/", "#"), "w") as cache:
            #     result[0] = name.decode('unicode-escape')
            #     cache.write(json.dumps(result))
        except Exception as e:
            print e
            # os.system("cp 'cache/%s' cache2/" % urlid.replace("/", "#"))
            with open("cache/%s" % urlid.replace("/", "#"), "w") as cache:
                result = dblp.getTitlesForAuthor((urlid, name))
                cache.write(json.dumps(result))
                # Sleep to avoid getting blocked by DBLP.
                time.sleep(0.5)

        authPubs.append(result)

    return (authPubs, dblpAuthorsList)

def getArgs():
    parser = argparse.ArgumentParser(description='MLJ matcher commmand line.', formatter_class=RawTextHelpFormatter)

    parser.add_argument('dbpath', metavar='D', type=str, nargs=1,
                        help='path to SQLite DB generated from DBLP XML dump.')

    parser.add_argument('inputpath', metavar='I', type=str, nargs=1,
                        help='PDF file(s) to use as input.')

    parser.add_argument('--output', dest='output',
                       default=os.path.curdir,
                       help='Output directory to save HTML and CSV files. Current directory by default.')

    parser.add_argument('--authors', dest='authors',
                        default=os.path.join(os.path.curdir, 'authors.txt'),
                        help="List of comma-separated author names and DBLP url IDs.\nLooks for 'authors.txt' in current directory by default."
                        )

    parser.add_argument('--indexby', dest='indexby',
                       default=1,
                       help="""Build semantic index using (1-5):
1. 53 EML articles: Latex sources
2. 247 EML articles: Latex sources
3. 53 EML articles: Latex sources + Wikipedia content
4. 247 EML articles: Latex sources + Wikipedia content
5. 729 EML articles: Latex sources + Wikipedia content""")

    parser.add_argument('--concatpubs', dest='concatpubs',
                        default='1',
                        help="Treat each author as a document of concatenated publication titles (default).\nIf this is set to 0, total contributions of individual publications are computed.")

    parser.add_argument('--special-cutoff', dest='specialcutoff',
                        default='-1',
                        help="Special members cutoff (checks for parentheses in names). None by default.")

    parser.add_argument('--others-cutoff', dest='otherscutoff',
                        default='-1',
                        help="Other members cutoff. None by default.")

    parser.add_argument('--topic-vector-entries', dest='numnonzero',
                        default=-1,
                        help="No. of non-zero entries in topic-space vectors. Keep original by default.")

    parser.add_argument('--num-topics', dest='numtopics',
                        default=3,
                        help="Number of topics to show, ordered by cosine similarity.")

    parser.add_argument('--cachedir', dest='cachedir',
                       default=os.path.join(os.path.curdir, 'cache'),
                       help='Directory to cache DBLP author publication data (if this directory exists,\nextra DBLP API calls are avoided and publications are read from the cache).')


    return parser.parse_args()

def main():
    args = getArgs()
    global CACHEDIR
    CACHEDIR = args.cachedir
    if not os.path.isdir(CACHEDIR):
        os.mkdir(CACHEDIR)
    if not os.path.isdir(args.output):
        os.mkdir(args.output)


    with open(args.authors, 'r') as fp:
        dblplist = fp.read()
    authPubs, dblpAuthorsList = getAuthPubs(dblplist, args.dbpath)
    encDirectory = indexby[args.indexby]
    matcher = Matcher(CACHEDIR, encDirectory)
    # print "Building semantic interpreter..."
    matcher.buildSemanticInterpreter()
    print "Building author profiles..."
    matcher.buildAuthorProfiles(authPubs)
    print "Building concatenated author profiles..."
    matcher.buildConcatenatedAuthorProfiles(authPubs)

    numtopics = args.numtopics

    templatePath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "views")
    template = Loader(templatePath).load("results.cli.html")

    for f in glob(args.inputpath[0]):
        with open(f, 'r') as fp:
            print "Extracting text from %s..." % f
            query = extractTextFromPDF(fp.read())
            print "Matching..."
            output = matcher.query(query, topK=args.numnonzero)
            concatscores = matcher.queryConcat(query, topK=args.numnonzero)
            queryConcepts = matcher.getTopConcepts(query, topK=args.numnonzero)

            sortconcat = False
            if args.concatpubs == 1:
                sortconcat = True
                output.sort(key=lambda x: concatscores[x[0][0].split("||")[1]][0], reverse=True)

            specialcutoff = getCutoff(args.specialcutoff)
            otherscutoff = getCutoff(args.otherscutoff)

            with open(os.path.join(args.output, os.path.split(f)[-1] + ".csv"), "w") as csv:
                for (author, score), _ in output:
                    name, url = author.split("||")
                    finalscore = concatscores[url][0] if sortconcat == True else score
                    if ("(" in name and ")" in name and finalscore >= specialcutoff) or (("(" not in name or ")" not in name) and finalscore >= otherscutoff):
                        csv.write("%s,%f\n" % (author.encode('utf-8'), finalscore))

            with open(os.path.join(args.output, os.path.split(f)[-1] + ".html"), "w") as html:
                html.write(template.generate(results=output,
                                    dblpPages=dict(dblpAuthorsList),
                                    concatscores=concatscores,
                                    specialcutoff=specialcutoff,
                                    otherscutoff=otherscutoff,
                                    sortconcat=sortconcat,
                                    numtopics=numtopics,
                                    queryconcepts=queryConcepts))



if __name__ == "__main__":
    main()

