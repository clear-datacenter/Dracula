import unittest
import theano
import theano.tensor
import numpy
import logging

from nn_layers import per_word_averaging_layer, embeddings_layer

import tensorflow as tf


class WordAveragingOpTests(unittest.TestCase):

    def test_embedding_layer(self):
        L = numpy.zeros((4, 4))
        L[0, :] = [0.2, 0.3, 0.4, 0.5]
        L[1, :] = [-0.2, -0.4, 0.6, 0.7]
        L[2, :] = [0.8, -0.2, 0.3, -0.1]
        L[3, :] = [-0.4, 0.2, 0.8, 0.9]

        l = tf.Variable(L, name='emb')

        P = numpy.zeros((4, 4))
        P[0, 0] = 1
        P[0, 1] = 2
        P[0, 3] = 3
        P[1, 0] = 1
        P[1, 1] = 2
        p = tf.constant(P, dtype='int32', name='char')

        init = tf.initialize_all_variables()
        sess = tf.Session()
        sess.run(init)

        R = embeddings_layer(p, l).eval(session=sess)

        self.assertTrue(numpy.allclose(R[0, 0], [-0.2, -0.4, 0.6, 0.7]))
        self.assertTrue(numpy.allclose(R[0, 1], [0.8, -0.2, 0.3, -0.1]))
        self.assertTrue(numpy.allclose(R[0, 3], [-0.4, 0.2, 0.8, 0.9]))
        self.assertTrue(numpy.allclose(R[1, 0], [-0.2, -0.4, 0.6, 0.7]))
        self.assertTrue(numpy.allclose(R[1, 1], [0.8, -0.2, 0.3, -0.1]))


    @classmethod
    def get_std(cls):
        n_samples, n_proj, n_chars = 2, 4, 4
        # n_chars -> maximum character sequence length (e.g. 140)
        # n_samples = minibatch size
        # n_proj = number of combined word/character embeddings
        n_chars, n_samples, n_proj = 4, 2, 4
        # Allocate a matrix which represents the LSTM layer output
        L = numpy.zeros((n_chars, n_samples, n_proj))
        L[1, 0, :] = [0.2, 0.3, 0.4, 0.5]
        L[2, 0, :] = [-0.2, -0.4, 0.6, 0.7]
        L[3, 0, :] = [0.8, -0.2, 0.3, -0.1]
        L[1, 1, :] = [-0.4, 0.2, 0.8, 0.9]

        W = numpy.zeros((n_chars, n_samples), dtype='int32')
        W[1, 0] = 1  # First tweet, first character to first word
        W[2, 0] = 1  # First tweet, second character to second word
        W[3, 0] = 2  # First tweet, third character to second word
        W[1, 1] = 1  # Second tweet, first character to second word

        # The expected output
        O = numpy.zeros((n_samples, 16, n_proj))
        O[0, 1, :] = [0.0, -0.05, 0.50, 0.60]  # First word, first tweet
        O[0, 2, :] = [0.8, -0.2, 0.3, -0.1]  # Second word, first tweet
        O[1, 1, :] = [-0.4, 0.2, 0.8, 0.9]  # First word, second tweet

        return n_chars, n_samples, n_proj, L, W, O

    def test_forward(self):

        n_chars, n_samples, n_proj, L, W, O = WordAveragingOpTests.get_std()

        for i in range(n_chars):
            for j in range(n_samples):
                W[i, j] = numpy.ravel_multi_index((i, j, W[i, j]), (n_chars, n_samples, 16))

        LArg = theano.tensor.dtensor3()
        WArg = theano.tensor.imatrix()

        out = per_word_averaging_layer(LArg, WArg, False)

        f = theano.function([LArg, WArg], out, on_unused_input='ignore')

        O_actual = f(L, W)

        self.assertTrue(numpy.allclose(O, O_actual))

    def test_forward_trimmed(self):

        n_chars, n_samples, n_proj, L, W, Oorig = WordAveragingOpTests.get_std()

        for i in range(n_chars):
            for j in range(n_samples):
                W[i, j] = numpy.ravel_multi_index((i, j, W[i, j]), (n_chars, n_samples, 16))

        # The expected output
        O = numpy.zeros((n_samples, 16, n_proj))
        O[0, 0, :] = [0.0, -0.05, 0.50, 0.60]  # First word, first tweet
        O[0, 1, :] = [0.8, -0.2, 0.3, -0.1]  # Second word, first tweet
        O[1, 0, :] = [-0.4, 0.2, 0.8, 0.9]  # First word, second tweet

        self.assertTrue(numpy.allclose(O[:, :-1], Oorig[:, 1:]))

        LArg = theano.tensor.dtensor3()
        WArg = theano.tensor.imatrix()

        out = per_word_averaging_layer(LArg, WArg, True)

        f = theano.function([LArg, WArg], out, on_unused_input='ignore')

        O_actual = f(L, W)

        print O
        print Oorig
        print O_actual

        self.assertTrue(numpy.allclose(O, O_actual))

    def test_numpy(self):
        n_chars, n_samples, n_proj, L, W, O = WordAveragingOpTests.get_std()

        # First index is the word index
        # Second is the character
        # Third is the batch index
        tmp = numpy.zeros((n_chars, n_samples, 16, n_proj))
        for i in range(n_chars):
            for j in range(n_samples):
                tmp[i, j, W[i, j], :] += L[i, j, :]

        divider = (tmp != 0).sum(axis=0)
        divider += (divider == 0.)  # Make sure we don't get NaN
        O_actual = tmp.sum(axis=0) / divider

        self.assertTrue(numpy.allclose(O_actual, O))

    def test_numpy_2(self):
        n_chars, n_samples, n_proj, L, W, O = WordAveragingOpTests.get_std()

        Wref = numpy.zeros(W.shape, dtype='int32')
        Wref[:, :] = W[:, :]
        for i in range(n_chars):
            for j in range(n_samples):
                print i, j, W[i, j]
                W[i, j] = numpy.ravel_multi_index((i, j, Wref[i, j]), (n_chars, n_samples, 16))

        # First index is the word index
        # Second is the character
        # Third is the batch index
        # tmp = np.reshape(L, (n_chars * n_samples, n_proj))[W.flatten()].reshape((n_chars, n_samples, 16, n_proj))
        tmpref = numpy.zeros((n_chars, n_samples, 16, n_proj))
        tmp = numpy.zeros((n_chars * n_samples * 16, n_proj))
        logging.debug(tmp.size)

        tmp[W.flatten()] = L.reshape((n_chars * n_samples, n_proj))
        tmp[W.flatten()] = L.reshape((n_chars * n_samples, n_proj))
        print W.flatten()
        logging.debug(tmp.size)
        tmp = numpy.reshape(tmp, (n_chars, n_samples, 16, n_proj))
        for i in range(n_chars):
            for j in range(n_samples):
                tmpref[i, j, Wref[i, j], :] += L[i, j, :]

        divider = (tmp != 0).sum(axis=0)
        divider += (divider == 0.)  # Make sure we don't get NaN
        O_actual = tmp.sum(axis=0) / divider

        self.assertTrue(numpy.allclose(O_actual, O))


if __name__ == "__main__":
    unittest.main()
