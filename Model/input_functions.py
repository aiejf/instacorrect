# -*- coding: utf-8 -*-
"""
Created on Mon Sep 11 16:57:28 2017

@author: maxime
"""
import tensorflow as tf

# Mapping of tf.example features used in two places. One for the two.
spec = {'input_sequence': tf.VarLenFeature(tf.int64),
        'input_sequence_length': tf.FixedLenFeature((), tf.int64,
                                                    default_value=0),
        'input_sequence_maxword': tf.FixedLenFeature((), tf.int64,
                                                     default_value=0),
        'output_sequence': tf.VarLenFeature(tf.int64),
        'output_sequence_length': tf.FixedLenFeature((), tf.int64,
                                                     default_value=0)}


def _parse_function(example_proto, at_training=True):
    """Function in charge of parsing a tf.example into a tensors"""
    to_return = ()
    # Parse the tf.example according to the features_spec definition
    parsed_features = tf.parse_single_example(example_proto, spec)
    # INPUTS
    # Sparse input tensor
    input_sparse = parsed_features['input_sequence']
    # Convert the sparse input to dense.
    input_dense = tf.sparse_to_dense(input_sparse.indices,
                                     input_sparse.dense_shape,
                                     input_sparse.values)
    # Convert it to a 4D tensor
    input_sl = parsed_features['input_sequence_length']
    input_ml = parsed_features['input_sequence_maxword']
    input_dense_2 = tf.reshape(input_dense,
                               tf.stack([tf.cast(input_sl, tf.int32),
                                         tf.cast(input_ml, tf.int32)]))
    to_return += (input_dense_2, input_sl)

    # OUTPUTS
    if at_training:
        output_sparse = parsed_features['output_sequence']
        output_sl = parsed_features['output_sequence_length']
        output_dense = tf.sparse_to_dense(output_sparse.indices,
                                          output_sparse.dense_shape,
                                          output_sparse.values)
        to_return += (output_dense, output_sl)

    return to_return


def bucketing_fn(sequence_length, buckets):
    """Given a sequence_length returns a bucket id"""
    # Clip the buckets at sequence length and return the first argmax,
    # the bucket id
    t = tf.clip_by_value(buckets, 0, sequence_length)
    return tf.argmax(t)


def reduc_fn(key, elements, window_size):
    """ Receives `window_size` elements """
    # Shuffle within each bucket
    return elements


def input_fn(filenames, batch_size, num_epochs, take=-1, skip=0, train=True):
    """
    Function to perform the data pipeline for the model.
    Should be wrapped around an anonymous function to set the parameters.
    Args:
        seq_filename: a string with the path for the tf.records to read
        batch_size: the batch size to use
        num_epochs: the number of times to read the entire dataset
    """
    # Create a dataset out of the raw TFRecord file. See the Data Generator
    dataset = tf.contrib.data.TFRecordDataset(filenames)
    # Skip X elements
    dataset = dataset.skip(skip)
    # Map the tf.example to tensor using the _parse_function
    dataset = dataset.map(_parse_function, num_threads=4)
    # If applicable only take `take`
    dataset = dataset.take(take)
    # Repeat the dataset for a given number of epoch
    dataset = dataset.repeat(num_epochs)
    # Create an arbitrary bucket range.
    buckets = [tf.constant(num, dtype=tf.int64) for num in range(0, 150, 2)]
    # Number of elements per bucket.
    window_size = 10*batch_size
    # Group the dataset according to a bucket key (see bucketing_fn).
    # Every element in the dataset is attributed a key (here a bucket id)
    # The elements are then bucketed according to these keys. A group of
    # `window_size` having the same keys are given to the reduc_fn.
    if train:
        dataset = dataset.group_by_window(lambda a, b, c, d:
                                          bucketing_fn(b, buckets),
                                          lambda key, x:
                                          reduc_fn(key, x, window_size),
                                          window_size)
    # We now have buckets of `window_size` size, let's batch and pad them
    dataset = dataset.padded_batch(batch_size, padded_shapes=(
        (tf.Dimension(None), tf.Dimension(None)),
        tf.TensorShape([]),
        tf.Dimension(None),
        tf.TensorShape([]),
    ))
    # Let's now make it a bit more easy to understand this dataset by mapping
    # each feature.
    dataset = dataset.map(lambda a, b, c, d:
                          ({"sequence": a, "sequence_length": b},
                           {"sequence": c, "sequence_length": d}
                           ))
    # Create the iterator to enumerate the elements of the dataset.
    iterator = dataset.make_one_shot_iterator()
    # Generator returned by the iterator.
    features, labels = iterator.get_next()
    return features, labels


def serving_input_receiver_fn():
    """An input receiver that expects a serialized tf.Example."""
    # Placeholder for the tf.example to be received
    serialized_tf_example = tf.placeholder(dtype=tf.string, shape=[None])
    # Dict to be passed to ServingInputReceiver -> input signature
    receiver_tensors = {'examples': serialized_tf_example}
    input_s, input_sl = _parse_function(serialized_tf_example[0],
                                        at_training=False)
    features = {'sequence': tf.expand_dims(input_s, 0),
                'sequence_length': tf.expand_dims(input_sl, 0)}
    return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)
