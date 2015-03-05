import tornado
import tornado.ioloop
import tornado.web
import os
from sm.util import extractTextFromPDF, DBLP, Matcher
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial, wraps
import tornado.ioloop
import tornado.web
import time, json, codecs
from sm.persist import Persist


EXECUTOR = ThreadPoolExecutor(max_workers=8)
PARALLEL_EXECUTOR = ProcessPoolExecutor(max_workers=4)
CACHEDIR = None
DBPATH = None

def getAuthPubs(dblplist):
    dblp = DBLP(DBPATH)
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

# def getAuthPubs(dblplist):
#     dbl = DBLP()
#     dblpAuthorsList = [i.split(",") for i in dblplist.split("\n") if i.strip() != '']
#     authPubs = list(Parallel(n_jobs=4, backend="threading")(delayed(dbl.getTitlesForAuthor, check_pickle=False)((urlid, name)) for name, urlid in dblpAuthorsList))
#     # print authPubs
#     return (authPubs, dblpAuthorsList)

def unblock(f):
    @tornado.web.asynchronous
    @wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]

        def callback(future):
            # try:
            self.write(future.result())
            # except:
            #     print "Caused an exception!"

            print future.result()
            self.write("E caused")

        EXECUTOR.submit(
            partial(f, *args, **kwargs)
        ).add_done_callback(
            lambda future: tornado.ioloop.IOLoop.instance().add_callback(
                partial(callback, future)))

    return wrapper

class Home(tornado.web.RequestHandler):
    def get(self):
        self.render(os.path.join(os.path.dirname(os.path.realpath(__file__)), "views/index.html"))
        
class Match(tornado.web.RequestHandler):
    # @unblock
    def post(self):
        self.query = Persist.query
        self.authPubs = Persist.authPubs
        self.dblpAuthorsList = Persist.dblpAuthorsList
        self.matcher = Persist.matcher

        self.write('<div id="progress">')
        self.flush()
        # Check if we're reading files or textareas
        if self.get_argument('inputtype') == "Raw Text":
            self.query = self.get_argument('inputtext')
            dblplist = self.get_argument('inputdblp')
        else:
            if len(self.request.files['uploadpdf']) > 1:
                print "GREATER THAN 1"
                self.query = {}
                for filecontent in self.request.files['uploadpdf']:
                    pdfBody = filecontent['body']
                    fileName = filecontent['filename']

                    def setQuery(fileName):
                        def setQuery2(query):
                            self.query[fileName] = query
                            print "ADDED", fileName
                        return setQuery2

                    print "Doing ", fileName
                    setQuery(fileName)(extractTextFromPDF(pdfBody))
                    print "Done ", fileName
                    # self.runThread(self.runParallel, ("Extracting text from PDF %s.<br>" % fileName, "<br>Finished extracting text from PDF %s.<br>" % fileName, extractTextFromPDF, pdfBody), callback=setQuery(fileName))
                    # self.query = extractTextFromPDF(pdfBody)

            else:
                pdfBody = self.request.files['uploadpdf'][0]['body']

                def setQuery(query):
                    self.query = query.result()

                self.runThread(self.runParallel, ("Extracting text from PDF.<br>", "<br>Finished extracting text from PDF.<br>", extractTextFromPDF, pdfBody), callback=setQuery)
                # self.query = extractTextFromPDF(pdfBody)


            dblplist = self.request.files['uploaddblp'][0]['body']
            # print dblplist

        def setAuthPubs(args):
            authPubs, dblpAuthorsList = args.result()
            self.authPubs = authPubs
            self.dblpAuthorsList = dblpAuthorsList

        def sleepUntilAvailable(tuple):
            numqueries = len(self.request.files['uploadpdf'])
            if 'query' in tuple and numqueries > 1:
                while True:
                    if None in [getattr(self, i) for i in tuple] or len(self.query) < numqueries:
                        time.sleep(1)
                        print "sleep"
                        print self.query.keys()
                    else:
                        break
            else:
                while True:
                    if None in [getattr(self, i) for i in tuple]:
                        time.sleep(1)
                        print 'sleep 2'
                    else:
                        break

        def waitAndFinish(matcher):
            sleepUntilAvailable(('authPubs', 'dblpAuthorsList'))

            if not matcher.builtAuthorProfiles: self.runThread2("Building author profiles...<br>", "<br>Finished building author profiles.<br>", matcher.buildAuthorProfiles, self.authPubs)
            if not matcher.builtConcatAuthorProfiles: self.runThread2("Building author profiles...<br>", "<br>Finished building author profiles.<br>", matcher.buildConcatenatedAuthorProfiles, self.authPubs)
            # matcher.buildAuthorProfiles(self.authPubs)
            # self.write("Building author profiles...<br>")
            # self.flush()
            # matcher.buildAuthorProfiles(self.authPubs)
            # self.write("<br>Finished building author profiles.<br>")
            # self.flush()

            sleepUntilAvailable(('query',))

            if type(self.query) == dict:
                output = []
                for filename, query in self.query.items():
                    print "Matching with %s" % filename
                    output.append((filename, matcher.query(query)))

                self.write("</div>")
                self.flush()
                self.render(os.path.join(os.path.dirname(os.path.realpath(__file__)), "views/multiresults.html"), results=output, dblpPages=dict(self.dblpAuthorsList))
            else:
                print "Matching!!"
                output = matcher.query(self.query)
                concatscores = matcher.queryConcat(self.query)
                print concatscores
                self.write("</div>")
                self.flush()
                self.render(os.path.join(os.path.dirname(os.path.realpath(__file__)), "views/results.html"), results=output, dblpPages=dict(self.dblpAuthorsList), concatscores=concatscores)

        if self.authPubs == None or self.dblpAuthorsList == None:
            self.runThread(self.runThread2, ("Fetching publications for given authors...<br>",
             "<br>Finished fetching publications.<br>", getAuthPubs, dblplist), callback=setAuthPubs)
        # setAuthPubs(getAuthPubs(dblplist))

        if self.matcher == None:
            self.matcher = Matcher(CACHEDIR)
            self.runThread2("Building semantic interpreter...<br>", "<br>Finished building semantic interpreter.<br>",
            self.matcher.buildSemanticInterpreter, callback=lambda x: self.runThread(waitAndFinish, (self.matcher,)))
        else:
            self.runThread(waitAndFinish, (self.matcher,))


        Persist.query = self.query
        Persist.authPubs = self.authPubs
        Persist.dblpAuthorsList = self.dblpAuthorsList
        Persist.matcher = self.matcher


        # self.runThread(wait)







        # matcher = Matcher(authPubs, profile=False)
        #
        # self.runParallel("Building semantic interpreter...<br>", "<br>Finished building semantic interpreter.<br>", matcher.buildSemanticInterpreter)
        # self.runParallel("Building author profiles...<br>", "<br>Finished building author profiles.<br>", matcher.buildAuthorProfiles)
        # # output = self.run("Matching...", matcher.query, (query,))
        # # import pickle
        # # try:
        # #     output = pickle.load(open("output", "rb"))
        # # except Exception as e:
        # #     print e
        # # matcher = Matcher(authPubs, profile=True)
        # output = matcher.query(query)
        # # pickle.dump(output, open("output", "wb"))
        #
        # self.render("results.html", results=output, dblpPages=dict(dblpAuthorsList))
        # self.finish(output)

    def getAuthPubs(self):
        dblp = DBLP()
        dblpAuthorsList = [i.split(",") for i in self.dblplist.split("\n")]
        authPubs = [(name, dblp.getTitlesForAuthor(urlid, name)) for name, urlid in dblpAuthorsList]
        return (authPubs, dblpAuthorsList)

    def runParallel(self, start, finish, fn, args=None):
        if args == None:
            fut = PARALLEL_EXECUTOR.submit(fn)
        else:
            fut = PARALLEL_EXECUTOR.submit(fn, args)
        self.write(start)
        self.flush()
        while True:
            if not fut.done():
                time.sleep(1)
                self.write("...")
                self.flush()
            else:
                break
        self.write(finish)
        self.flush()
        return fut.result()

    def runThread2(self, start, finish, fn, args=None, callback=None):
        if args == None:
            fut = EXECUTOR.submit(fn)
        else:
            fut = EXECUTOR.submit(fn, args)
        self.write(start)
        self.flush()
        while True:
            if not fut.done():
                time.sleep(1)
                self.write("...")
                self.flush()
            else:
                break
        self.write(finish)
        self.flush()
        if callback == None:
            return fut.result()
        else:
            fut.add_done_callback(callback)

    def runThread(self, fn, args=None, callback=None):
        if args == None:
            fut = EXECUTOR.submit(fn)
        else:
            fut = EXECUTOR.submit(fn, *args)
        # fut = EXECUTOR.submit(fn)
        if callback == None:
            return fut.result()
        else:
            fut.add_done_callback(callback)

    def run(self, start, finish, fn, args=None):
        if args != None:
            fut = EXECUTOR.submit(fn, args)
        else:
            fut = EXECUTOR.submit(fn)
        self.write(start)
        self.flush()
        while True:
            if not fut.done():
                time.sleep(1)
                self.write("...")
                self.flush()
            else:
                break
        self.write(finish)
        self.flush()
        return fut.result()

        # dblpAuthorsList = [i.split(",") for i in self.get_argument('inputdblp').split("\n")]
        # authPubs = [(name, dblp.getTitlesForAuthor(urlid)) for name, urlid in dblpAuthorsList]
        # # query = extractTextFromPDF(self.request.files['uploadpdf'][0]['body'])
        # query = self.get_argument('inputtext')
        # matcher = Matcher(authPubs)
        # self.finish(matcher.query(query))

        # self.finish(extractTextFromPDF(self.request.files['uploadpdf'][0]['body']))
        # self.finish("BLAHL" + str(self.get_argument('inputtext', "idwmemwe")))
 
application = tornado.web.Application([
        (r"/", Home),
        (r"/upload", Match),
        (r"/css/(.*)", tornado.web.StaticFileHandler),
        (r"/js/(.*)", tornado.web.StaticFileHandler),
        ], debug=True, static_path=os.path.join(os.path.dirname(__file__), "static"),)
 

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Start MLJ Matcher server.')

    parser.add_argument('dbpath', metavar='D', type=str, nargs=1,
                   help='path to SQLite DB generated from DBLP XML dump')

    parser.add_argument('--port', dest='port', action='store_const',
                   const=8080, default=8080,
                   help='Port to start the HTTP server at (8080 by default)')

    parser.add_argument('--cachedir', dest='cachedir', action='store_const',
                   const=os.path.join(os.path.curdir, 'cache'), default=os.path.join(os.path.curdir, 'cache'),
                   help='Directory to cache DBLP author publication data (if this directory exists, extra DBLP API calls are avoided and publications are read from the cache)')


    args = parser.parse_args()

    global CACHEDIR, DBPATH
    CACHEDIR = args.cachedir
    if not os.path.isdir(CACHEDIR):
        os.mkdir(CACHEDIR)

    DBPATH = args.dbpath

    application.listen(args.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()