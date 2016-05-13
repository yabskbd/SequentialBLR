# Functions used for Tensorflow training model
# Filename:     tf_functions.py
# Author:       apadin
# Start Date:   5/13/2016

import numpy as np
import tensorflow as tf

graph = tf.Graph()

debug = 1

## Tensorflow Train ###
def tf_train(X_train, y_train):

    before_time = time.time() #debug

    # In order to prevent memory leaks from re-making the graph every time,
    # must clear the operations from the graph on each run
    with graph.as_default():

        graph.__init__() # clear operations
        

        # First turn y_train into a [n, 1] matrix
        y_train = np.reshape(y_train, (len(y_train), 1))

        # If data values are too large, analysis will not converge
        # Divide both X and y by the same value so that W is not affected
        (X_rows, X_cols) = np.shape(X_train)
        divisor = min(X_train.max(), y_train.max())

        for (x, y), value in np.ndenumerate(X_train):
            X_train[x, y] /= divisor

        for (x, y), value in np.ndenumerate(y_train):
            y_train[x, y] /= divisor

        W = tf.Variable(tf.zeros([X_cols, 1]))      # Weight matrix
        b = tf.Variable(tf.zeros([1]))

        # y = W*x
        y = tf.matmul(X_train, W)

        # Minimize the mean squared errors
        loss = tf.reduce_mean(tf.square(y - y_train))
        train_step = tf.train.GradientDescentOptimizer(0.5).minimize(loss)

        # Initialize variables and session
        init = tf.initialize_all_variables()
        sess = tf.Session()
        sess.run(init)

        # Train the model
        for iter in xrange(100):
            sess.run(train_step)

        # Return the model parameters
        if debug:
            print 'Training Loss:', sess.run(loss)

        w_opt = np.transpose(sess.run(W))

        if debug:
            print "Time elapsed: ", time.time() - before_time
        
        return w_opt
