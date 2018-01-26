# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division

import tensorflow as tf

from niftynet.layer.base_layer import Layer
from niftynet.layer.layer_util import \
    expand_spatial_params, infer_spatial_rank
from niftynet.utilities.util_common import look_up_operations

"""
This class approximates image smoothing using separable 1D kernels.
(This layer is not trainable.)
"""


def gaussian_1d(sigma, truncated=3.0):
    if sigma == 0:
        return tf.constant(0.0)

    tail = int(sigma * truncated)
    k = [(-0.5 * x * x) / (sigma * sigma) for x in range(-tail, tail + 1)]
    k = tf.exp(k)
    k = k / tf.reduce_sum(k)
    return k


def cauchy_1d(sigma, truncated=5.0):
    if sigma == 0:
        return tf.constant(0.0)

    tail = int(sigma * truncated)
    k = [((float(x) / sigma) ** 2 + 1.0) for x in range(-tail, tail + 1)]
    k = tf.reciprocal(k)
    k = k / tf.reduce_sum(k)
    return k


SUPPORTED_KERNELS = {'gaussian': gaussian_1d, 'cauchy': cauchy_1d}


class SmoothingLayer(Layer):
    def __init__(self, sigma=1, truncate=3.0, type_str='gaussian'):
        Layer.__init__(self, name='approximated_smoothing')
        self.kernel_func = look_up_operations(
            type_str.lower(), SUPPORTED_KERNELS)
        self.sigma = float(sigma)
        self.truncate = float(truncate)

    def layer_op(self, image):
        spatial_rank = infer_spatial_rank(image)
        _sigmas = expand_spatial_params(
            input_param=self.sigma, spatial_rank=spatial_rank)
        _truncate = expand_spatial_params(
            input_param=self.truncate, spatial_rank=spatial_rank)

        def do_conv(input_tensor, dim):
            assert dim < spatial_rank
            if dim < 0:
                return input_tensor

            # squeeze the kernel to be along the 'dim'
            new_kernel_shape = [1] * (spatial_rank + 2)
            new_kernel_shape[dim] = -1
            kernel_tensor = self.kernel_func(
                sigma=_sigmas[dim], truncated=_truncate[dim])
            kernel_tensor = tf.reshape(kernel_tensor, new_kernel_shape)

            # split channels and do smoothing respectively
            chn_wise_list = tf.unstack(do_conv(input_tensor, dim - 1), axis=-1)
            output_tensor = [
                tf.nn.convolution(input=tf.expand_dims(chn, axis=-1),
                                  filter=kernel_tensor,
                                  padding='SAME',
                                  strides=[1] * spatial_rank)
                for chn in chn_wise_list]
            return tf.concat(output_tensor, axis=-1)

        return do_conv(image, spatial_rank - 1)
