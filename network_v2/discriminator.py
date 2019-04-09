import numpy as np
import tensorflow as tf

from network_v2.official_code_ops import blur2d, downscale2d, minibatch_stddev_layer
from network_v2.common_ops import (
    equalized_dense, equalized_conv2d, conv2d_downscale2d, apply_bias, lerp_clip
)


def discriminator_block(x, res, n_f0, n_f1):
    gain = np.sqrt(2)
    lrmul = 1.0
    with tf.variable_scope('{:d}x{:d}'.format(res, res)):
        with tf.variable_scope('Conv0'):
            x = equalized_conv2d(x, n_f0, kernel=3, gain=gain, lrmul=lrmul)
            x = apply_bias(x, lrmul=lrmul)
            x = tf.nn.leaky_relu(x)

        with tf.variable_scope('Conv1_down'):
            x = blur2d(x, [1, 2, 1])
            x = conv2d_downscale2d(x, n_f1, kernel=3, gain=gain, lrmul=lrmul)
            x = apply_bias(x, lrmul=lrmul)
            x = tf.nn.leaky_relu(x)
    return x


def discriminator_last_block(x, res, n_f0, n_f1):
    gain = np.sqrt(2)
    lrmul = 1.0
    with tf.variable_scope('{:d}x{:d}'.format(res, res)):
        x = minibatch_stddev_layer(x, group_size=4, num_new_features=1)
        with tf.variable_scope('Conv0'):
            x = equalized_conv2d(x, n_f0, kernel=3, gain=gain, lrmul=lrmul)
            x = apply_bias(x, lrmul=lrmul)
            x = tf.nn.leaky_relu(x)
        with tf.variable_scope('Dense0'):
            x = equalized_dense(x, n_f1, gain=gain, lrmul=lrmul)
            x = apply_bias(x, lrmul=lrmul)
            x = tf.nn.leaky_relu(x)
        with tf.variable_scope('Dense1'):
            x = equalized_dense(x, 1, gain=1.0, lrmul=lrmul)
            x = apply_bias(x, lrmul=lrmul)
    return x


def fromrgb(x, res, n_f):
    with tf.variable_scope('{:d}x{:d}'.format(res, res)):
        with tf.variable_scope('FromRGB'):
            x = equalized_conv2d(x, fmaps=n_f, kernel=1, gain=np.sqrt(2), lrmul=1.0)
            x = apply_bias(x, lrmul=1.0)
            x = tf.nn.leaky_relu(x)
    return x


def smooth_transition(prv, cur, res, transition_res, alpha):
    # alpha == 1.0: use only previous resolution output
    # alpha == 0.0: use only current resolution output

    with tf.variable_scope('{:d}x{:d}'.format(res, res)):
        with tf.variable_scope('smooth_transition'):
            # use alpha for current resolution transition
            if transition_res == res:
                out = lerp_clip(cur, prv, alpha)

            # ex) transition_res=32, current_res=16
            # use res=16 block output
            else:   # transition_res > res
                out = lerp_clip(cur, prv, 0.0)
    return out


def discriminator(image, alpha, resolutions, featuremaps):
    # check input parameters
    assert len(resolutions) == len(featuremaps)
    assert len(resolutions) >= 2

    # discriminator's (resolutions and featuremaps) are reversed against generator's
    r_resolutions = resolutions[::-1]
    r_featuremaps = featuremaps[::-1]

    # use smooth transition on only current training resolution
    transition_res = r_resolutions[0]

    with tf.variable_scope('discriminator', reuse=tf.AUTO_REUSE):
        # set inputs
        img = image
        x = fromrgb(image, r_resolutions[0], r_featuremaps[0])

        # stack discriminator blocks
        for index, (res, n_f) in enumerate(zip(r_resolutions[:-1], r_featuremaps[:-1])):
            res_next = r_resolutions[index + 1]
            n_f_next = r_featuremaps[index + 1]

            x = discriminator_block(x, res, n_f, n_f_next)
            img = downscale2d(img)
            y = fromrgb(img, res_next, n_f_next)
            x = smooth_transition(y, x, res, transition_res, alpha)

        # last block
        res = r_resolutions[-1]
        n_f = r_featuremaps[-1]
        x = discriminator_last_block(x, res, n_f, n_f)

        scores_out = tf.identity(x, name='scores_out')
    return scores_out


def test_discriminator_network(resolutions, featuremaps):
    from utils.utils import print_variables

    # prepare variables
    zero_init = tf.initializers.zeros()
    input_image_res = resolutions[-1]
    alpha = tf.get_variable('alpha', shape=[], dtype=tf.float32, initializer=zero_init, trainable=False)

    fake_images = tf.constant(0.5, dtype=tf.float32, shape=[1, 3, input_image_res, input_image_res])
    fake_score = discriminator(fake_images, alpha, resolutions, featuremaps)

    print(fake_score.shape)
    print_variables()
    return


def main():
    # original
    resolutions = [4, 8, 16, 32, 64, 128, 256, 512, 1024]
    featuremaps = [512, 512, 512, 512, 256, 128, 64, 32, 16]
    test_discriminator_network(resolutions, featuremaps)

    # # reduced
    # resolutions = [4, 8]
    # featuremaps = [512, 512]
    # test_discriminator_network(resolutions, featuremaps)
    return


if __name__ == '__main__':
    main()