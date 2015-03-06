import numpy as np
from scipy.sparse import issparse

__author__ = 'nilesh'

class CosineQuery():
    def __init__(self, semanticProfile):
        """Takes profiles generated from input documents and runs queries against them.

        Args:
            semanticProfile: SemanticProfile built from input documents and knowledge base.
        """

        self.semanticProfile = semanticProfile
        self.labels = semanticProfile.documentLabels
        self.conceptLabels = semanticProfile.conceptLabels

    def _query(self, x, numResults=None):
        resultScores = x.dot(self.semanticProfile.features.T)
        if issparse(resultScores):
            resultScores = resultScores.toarray()[0]
        if numResults != None:
            selectedIndices = np.argsort(resultScores)[-numResults:].tolist()
        else:
            selectedIndices = np.argsort(resultScores).tolist()
        selectedIndices.reverse()

        resultScores = resultScores[selectedIndices].tolist()
        resultLabels  = [self.labels[i] for i in selectedIndices]
        resultVectors = [self.semanticProfile.features[i] for i in selectedIndices]

        return resultLabels, resultScores, resultVectors

    def query(self, x, numResults=None):
        """Query vector x against semanticProfile

        Args:
            x: Sparse row vector with same number of columns as semanticProfile.features
                Use semanticProfile.transformRawDocuments to create this.
            numResults: Number of results to fetch.

        Returns:
            list of tuples (label, score, vector) where vector is a result row vector, label is the corresponding label
            obtained from Dictionary.documentLabels, and score is the cosine similarity score between x and vector.
        """
        labels, scores, vectors = self._query(x, numResults)
        return zip(labels, scores, vectors)

    def queryContributions(self, x, numResults=None, topConcepts=-1):
        """Query vector x against semanticProfile and return matches along with corresponding contributions from the
        topConcept matching concepts. Use this to know which semantic concepts the query and result have most in common.

        Args:
            x: Sparse row vector with same number of columns as semanticProfile.features
                Use semanticProfile.transformRawDocuments to create this.
            numResults: Number of results to fetch.
            topConcepts: Number of matching concepts to fetch for each match.

        Returns:
            list of tuples (label, score, vector, concepts) where vector is a result row vector, label is the
            corresponding label obtained from Dictionary.documentLabels, score is the cosine similarity score between x
            and vector, and concepts is a mapping from concept labels to contribution scores (inner product elements).
        """

        labels, scores, vectors = self._query(x, numResults)
        concepts = []
        if issparse(x):
            x = x.toarray()[0]

        for v in vectors:
            if issparse(v):
                v = v.toarray()[0]

            products = x*v
            if topConcepts == -1:
                topContributions = np.argsort(products).tolist()
            else:
                topContributions = np.argsort(products)[-topConcepts:].tolist()
            for i in topContributions:
                if products[i] == 0.0:
                    topContributions.remove(i)
            concepts += [{self.conceptLabels[i]:products[i] for i in topContributions}]

        return zip(labels, scores, vectors, concepts)


class LshQuery():
    def __init__(self, semanticProfile, lshIndex):
        """Takes profiles generated from input documents and runs queries against them.

        Args:
            semanticProfile: SemanticProfile built from input documents and knowledge base.
            lshIndex: LshIndex
        """

        self.semanticProfile = semanticProfile
        self.labels = semanticProfile.documentLabels
        self.conceptLabels = semanticProfile.conceptLabels
        self.lsh = lshIndex.lsh

    def _query(self, x, numResults):
        resultScores = []
        resultLabels = []
        resultVectors = []
        for result in self.lsh.query(x, num_results=numResults):
            resultVectors += [result[0][0]]
            resultLabels += [result[0][1]]
            resultScores += [1.0 - result[1]]

        return resultLabels, resultScores, resultVectors

    def query(self, x, numResults=10):
        """Query vector x against semanticProfile

        Args:
            x: Sparse row vector with same number of columns as semanticProfile.features
                Use semanticProfile.transformRawDocuments to create this.
            numResults: Number of results to fetch.

        Returns:
            list of tuples (label, score, vector) where vector is a result row vector, label is the corresponding label
            obtained from Dictionary.documentLabels, and score is the cosine similarity score between x and vector.
        """
        labels, scores, vectors = self._query(x, numResults)
        return zip(labels, scores, vectors)

    def queryContributions(self, x, numResults=10, topConcepts=5):
        """Query vector x against semanticProfile and return matches along with corresponding contributions from the
        topConcept matching concepts. Use this to know which semantic concepts the query and result have most in common.

        Args:
            x: Sparse row vector with same number of columns as semanticProfile.features
                Use semanticProfile.transformRawDocuments to create this.
            numResults: Number of results to fetch.
            topConcepts: Number of matching concepts to fetch for each match.

        Returns:
            list of tuples (label, score, vector, concepts) where vector is a result row vector, label is the
            corresponding label obtained from Dictionary.documentLabels, score is the cosine similarity score between x
            and vector, and concepts is a mapping from concept labels to contribution scores (inner product elements).
        """

        labels, scores, vectors = self._query(x, numResults)
        concepts = []
        if issparse(x):
            x = x.toarray()[0]

        for v in vectors:
            if issparse(v):
                v = v.toarray()[0]

            products = x*v
            topContributions = np.argsort(products)[-topConcepts:]
            concepts += [{self.conceptLabels[i]:products[i] for i in topContributions}]

        return zip(labels, scores, vectors, concepts)