from sklearn.feature_extraction.text import CountVectorizer
from nltk.tokenize import RegexpTokenizer
from nltk.stem.porter import *
from nltk.corpus import stopwords
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import lil_matrix
import numpy as np
from sklearn.preprocessing import normalize
from sparselsh import LSH

__author__ = 'nilesh'

# tokenizer = RegexpTokenizer(r'\w+')
# stemmer = PorterStemmer()
# stop = stopwords.words('english')
# def getWords(text):
#     # text = text.decode('utf-8', 'ignore')
#     try:
#         doc = re.sub(' +', ' ', text).replace('\n', ' ')
#     except Exception as e:
#         print text
#         raise e
#     tokens = tokenizer.tokenize(doc)
#     tokens = [stemmer.stem(i.lower()) for i in tokens if i not in stop and not i.isdigit() and len(i) > minWordLen]
#     return " ".join(tokens)
#
# def clean(rawDocuments, minWordLength):
#     currentThreadName = threading.currentThread().getName()
#     threading.currentThread().setName("MainThread")
#     global minWordLen
#     minWordLen = minWordLength
#     """Returns a list of cleaned and processed strings (stemming, stopword removal etc.)"""
#     # return [getWords(doc) for doc in rawDocuments]
#     cleaned = list(Parallel(n_jobs=4)(delayed(getWords)(doc) for doc in rawDocuments))
#     # threading.currentThread().setName(currentThreadName)
#     return cleaned

def clean(rawDocuments, minWordLength):
        """Returns a list of cleaned and processed strings (stemming, stopword removal etc.)"""
        tokenizer = RegexpTokenizer(r'\w+')
        stemmer = PorterStemmer()
        stop = stopwords.words('english')
        def getWords(text):
            # try:
            doc = re.sub(' +', ' ', text).replace('\n', ' ')
            # except Exception as e:
            #     print text
            #     raise e
            tokens = tokenizer.tokenize(doc)
            tokens = [stemmer.stem(i.lower()) for i in tokens if i not in stop and not i.isdigit() and len(i) > minWordLength]
            return " ".join(tokens)
        return [getWords(doc) for doc in rawDocuments]


class Dictionary():
    def __init__(self, rawDocuments, documentLabels, ngramRange=3, maxTerms=100000, minWordLength=3):
        """Cleans rawDocuments, extracts unique terms and builds a dictionary.

        Args:
            rawDocuments: a list of raw unicode strings, each representing a single document.
            documentLabels: List of extra data to store for each document.
                            documentLabels[i] should contain the id or title for rawDocuments[i]
            ngramRange: select word k-grams for k = [1..ngramRange].
            maxTerms: select only top maxTerms terms, ordered by global term frequency (i.e. size of vocabulary).
            minTermLength: minimum length of words to include.
        """

        self.documentLabels = documentLabels
        self.minWordLength = minWordLength
        self.cleanedDocuments = clean(rawDocuments, minWordLength)
        self.count = CountVectorizer(ngram_range=(1, ngramRange), max_features=maxTerms)
        self.count.fit(self.cleanedDocuments)


class LshIndex():
    def __init__(self, semanticProfile, hashSize, numHashtables, matrixFile, berkeleydbFile):
        """Creates locality sensitive hashing index using a SemanticProfile.

        Args:
            semanticProfile: SemanticProfile built from input documents and knowledge base.
            hashSize:  Number of bits in resulting binary hash.
            numHashtables: The number of hash tables used for multiple look-ups.
                            Increasing the number of hashtables increases the probability of
                            a hash collision of similar documents, but it also increases the
                            amount of work needed to add points.
            matrixFile: compressed numpy file ending with extension `.npz`, where the uniform random planes will be stored.
            berkeleydbFile: file to store Berkeley DB backend.
        """

        X = semanticProfile.features
        labels = semanticProfile.documentLabels

        self.lsh = LSH(hash_size=hashSize,
                  input_dim=X.shape[1],
                  num_hashtables=numHashtables,
                  matrices_filename=matrixFile,
                  overwrite=True)

        for i in xrange(X.shape[0]):
            x = X.getrow(i)
            self.lsh.index(x, extra_data=labels[i])


class SemanticProfile():
    def __init__(self,
                 documentsDictionary,
                 semanticInterpreterDictionary,
                 ngramRange=3,
                 numSingularVectors=100,
                 topKConcepts=5):
        """Cleans rawDocuments, extracts unique terms and builds a dictionary.

        Args:
            documentsDictionary: Dictionary built from input documents.
            semanticInterpreterDictionary: Dictionary built from documents from knowledge base.
            ngramRange: select word k-grams for k = [1..ngramRange].
            numSingularVectors: Number of singular vectors to keep in truncated SVD.
        """
        self.minWordLength = documentsDictionary.minWordLength
        self.documentLabels = documentsDictionary.documentLabels
        self.conceptLabels = semanticInterpreterDictionary.documentLabels
        self.topKConcepts = topKConcepts

        self.jointVocabulary = list(set([i for i in documentsDictionary.count.vocabulary_])
                                    .union(set([k for k in semanticInterpreterDictionary.count.vocabulary_])))

        self.documentsTfidf = TfidfVectorizer(ngram_range=(1, ngramRange), vocabulary=self.jointVocabulary,
                                              sublinear_tf=True)
        D = self.documentsTfidf.fit_transform(documentsDictionary.cleanedDocuments)

        self.semanticIntTfidf = TfidfVectorizer(ngram_range=(1, ngramRange), vocabulary=self.jointVocabulary)
        T = self.semanticIntTfidf.fit_transform(semanticInterpreterDictionary.cleanedDocuments)

        E = D.dot(T.T) # E = D x T'

        self.svd = TruncatedSVD(n_components=numSingularVectors, random_state=0)
        # self.features = self.svd.fit_transform(self.trim(E, K=self.topKConcepts))
        self.features = normalize(self.trim(E, K=self.topKConcepts))
        self.T = T
        self.E = E


    def trim(self, E, K):
        E = E.tolil()
        for i in range(E.shape[0]):
            row = E[i].toarray()[0]
            row[np.argsort(row)[:-K]] = 0.0
            E[i] = lil_matrix(row)
        return E.tocsr()

    def transformRawDocuments(self, docs):
        D = self.documentsTfidf.transform(clean(docs, self.minWordLength))
        E = D.dot(self.T.T)
        # return self.svd.transform(self.trim(E, K=self.topKConcepts))
        return normalize(self.trim(E, K=self.topKConcepts))

